"""개발자용 관광수요 기반 지역 후보 비교. Python 3.10+, 외부 패키지 불필요.

입력: 직접 정규화한 한국관광 데이터랩 CSV(공식 다운로드 원본 그대로는 아님).
공급 부족, 반려견 수요, 장소 이용조건, 코스 추천은 분석하지 않음. 반려동물 시설 공급은 analyze_pet_supply.py에서 별도로 결합한다.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from statistics import mean

FIELDS = ["region_code", "region_name", "region_level", "month",
          "visitors", "overnight_pct", "visitor_source", "overnight_source"]
ANALYSIS_MONTHS = 11


def months_between(start, end, *, expected_count=None):
    def index(value):
        if not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", value):
            raise ValueError("월 형식: YYYY-MM")
        year, month = map(int, value.split("-"))
        if year == 0:
            raise ValueError("연도는 0001 이상이어야 합니다.")
        return year * 12 + month - 1
    a, b = index(start), index(end)
    if b < a:
        raise ValueError("종료 월은 시작 월 이후여야 합니다.")
    count = b - a + 1
    if expected_count is not None and count != expected_count:
        raise ValueError(f"시작~종료 기간은 연속된 {expected_count}개월이어야 합니다.")
    return {f"{i // 12:04d}-{i % 12 + 1:02d}" for i in range(a, b + 1)}


def percentile(values):
    """평균 동률 순위: (rank - 1)/(n - 1). 상수 지표는 모두 0.5."""
    n = len(values)
    if n < 2:
        raise ValueError("비교 지역은 2곳 이상 필요합니다.")
    return [(sum(x < v for x in values) + (sum(x == v for x in values) - 1) / 2)
            / (n - 1) for v in values]


def read_regions(path, months, level, *, input_bytes=None):
    groups = defaultdict(dict)
    names = {}
    levels = {}
    errors = []
    if input_bytes is None:
        input_bytes = path.read_bytes()
    with io.StringIO(input_bytes.decode("utf-8-sig"), newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        if not reader.fieldnames or set(FIELDS) - set(reader.fieldnames):
            raise ValueError("필수 열: " + ",".join(FIELDS))
        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError("중복된 열 이름: CSV 헤더를 확인하세요.")
        for line, row in enumerate(reader, 2):
            try:
                if None in row:
                    raise ValueError("열 개수 초과: 숫자 쉼표/CSV 따옴표 확인")
                row = {k: (row.get(k) or "").strip() for k in FIELDS}
                if any(not value for value in row.values()):
                    raise ValueError("필수 값 누락(결측을 0으로 채우지 말 것)")
                if level == "city":
                    if row["region_level"] not in {"sido", "sigungu"} or not row["region_name"].endswith("시"):
                        raise ValueError("시 전체 비교에는 광역시·특별시·특별자치시 또는 기초시 전체 자료가 필요합니다.")
                elif row["region_level"] != level:
                    raise ValueError("시도·시군구 혼합 또는 지정 단위 불일치")
                if not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", row["month"]):
                    raise ValueError("월 형식: YYYY-MM (예: 2025-03)")
                if row["month"] not in months:
                    raise ValueError("분석 기간 밖의 월")
                code = row["region_code"]
                if code in names and names[code] != row["region_name"]:
                    raise ValueError("같은 지역코드의 지역명 불일치")
                if code in levels and levels[code] != row["region_level"]:
                    raise ValueError("같은 지역코드의 원자료 행정 단위 불일치")
                if row["month"] in groups[code]:
                    raise ValueError("지역코드+월 중복")
                v = float(row["visitors"].replace(",", ""))
                o = float(row["overnight_pct"])
                if not math.isfinite(v) or v < 0:
                    raise ValueError("방문 지표는 유한한 0 이상 숫자 필요")
                if not math.isfinite(o) or not 0 <= o <= 100:
                    raise ValueError("숙박비율은 0~100 숫자(예: 23.5), % 기호 제외")
                names[code] = row["region_name"]
                levels[code] = row["region_level"]
                groups[code][row["month"]] = (v, o, row["visitor_source"], row["overnight_source"])
            except ValueError as exc:
                errors.append(f"행 {line}: {exc}")
    for code, records in groups.items():
        missing = months - records.keys()
        if missing:
            errors.append(f"{code}: 누락 월 {', '.join(sorted(missing))}")
    if len(groups) < 2:
        errors.append("비교 지역 2곳 이상 필요")
    if level == "city":
        province_codes = {code for code, source_level in levels.items() if source_level == "sido"}
        if any(code[:2] in province_codes for code, source_level in levels.items() if source_level == "sigungu"):
            errors.append("범위가 겹치는 광역시와 산하 기초지역을 동시에 비교할 수 없습니다.")
    if errors:
        raise ValueError("\n".join(errors[:25]))
    return [{"region_code": code, "region_name": names[code], "region_level": levels[code],
             "mean_monthly_visitors": mean(x[0] for x in records.values()),
             "mean_monthly_overnight_pct": mean(x[1] for x in records.values()),
             "months": len(records),
             "source_files": ";".join(sorted({s for x in records.values() for s in x[2:]}))}
            for code, records in sorted(groups.items())]


def score_regions(regions):
    v = percentile([r["mean_monthly_visitors"] for r in regions])
    o = percentile([r["mean_monthly_overnight_pct"] for r in regions])
    # 순위는 항상 1 / (2 * (N - 1))의 배수다. 유리수로 복원해
    # 30.0과 30.000000000000004 같은 오차로 공동 순위가 갈리는 것을 막는다.
    denominator = 2 * (len(regions) - 1)
    exact_v = [Fraction(round(x * denominator), denominator) for x in v]
    exact_o = [Fraction(round(x * denominator), denominator) for x in o]
    scenarios = {"base": Fraction(7, 10), "balanced": Fraction(1, 2),
                 "visitors_only": Fraction(1)}
    exact_scores = {name: [100 * (weight * x + (1 - weight) * y)
                          for x, y in zip(exact_v, exact_o)]
                    for name, weight in scenarios.items()}
    for i, row in enumerate(regions):
        row["visitor_percentile"] = v[i]
        row["overnight_percentile"] = o[i]
        for name in scenarios:
            row[f"score_{name}"] = float(exact_scores[name][i])
    for name in scenarios:
        scores = exact_scores[name]
        for i, row in enumerate(regions):
            # 동점은 같은 등수. 지역코드는 출력 정렬에만 사용.
            row[f"rank_{name}"] = 1 + sum(x > scores[i] for x in scores)
    return sorted(regions, key=lambda r: (-r["score_base"], r["region_code"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--start", required=True, help="YYYY-MM")
    parser.add_argument("--end", required=True, help="YYYY-MM")
    parser.add_argument("--level", required=True, choices=["sido", "sigungu", "city"],
                        help="city: 광역시·기초시 전체 비교. 원자료 행정 등급은 유지합니다.")
    parser.add_argument("--output", required=True, type=Path, help="새 결과 폴더")
    parser.add_argument("--synthetic", action="store_true", help="가상 자료 검증 실행임을 결과에 표시")
    args = parser.parse_args()
    try:
        months = months_between(args.start, args.end, expected_count=ANALYSIS_MONTHS)
        # 계산과 해시에 동일한 파일 스냅샷을 사용한다.
        input_bytes = args.input.read_bytes()
        ranked = score_regions(read_regions(args.input, months, args.level, input_bytes=input_bytes))
        # 기존 결과의 우발적 덮어쓰기 방지. 실행마다 새 폴더 사용.
        args.output.mkdir(parents=True, exist_ok=False)
        with (args.output / "region_ranking.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(ranked[0]))
            writer.writeheader()
            writer.writerows(ranked)
        warnings = ["관광수요 기반 개발 후보. 반려견 수요·공급 부족 미검증.",
                    "월별 방문값 평균: 연간 고유 관광객 수가 아님.",
                    f"숙박비율: {ANALYSIS_MONTHS}개 월별 비율의 단순평균, 연간 방문자 가중 비율이 아님.",
                    "단위·원자료 집계 정의·행정경계 일치는 개발자의 사전 확인 필요."]
        if args.synthetic:
            warnings.insert(0, "가상 자료를 사용한 실행 검증. 실제 지역 선정에 사용할 수 없음.")
        if args.level == "city":
            warnings.append("시 전체를 서비스 범위로 비교합니다. 광역시·기초시 집계 기준 및 면적·인구 차이가 있으며 인구·면적 보정은 하지 않았습니다.")
        if any(len({r[key] for r in ranked}) == 1 for key in
               ["mean_monthly_visitors", "mean_monthly_overnight_pct"]):
            warnings.append("지역 간 값이 같은 지표 존재: 해당 지표의 순위 구분 능력 없음.")
        review = {"status": "developer_review_required",
                  "source": "Synthetic fixture" if args.synthetic else "Korea Tourism Data Lab",
                  "data_kind": "synthetic" if args.synthetic else "user_supplied",
                  "period": [args.start, args.end],
                  "analysis_month_count": len(months),
                  "region_level": "mixed" if args.level == "city" else args.level,
                  "comparison_scope": "whole_city" if args.level == "city" else args.level,
                  "source_region_levels": sorted({row["region_level"] for row in ranked}),
                  "compared_region_count": len(ranked),
                  "weights": {"base": [0.7, 0.3], "balanced": [0.5, 0.5], "visitors_only": [1, 0]},
                  "created_utc": datetime.now(timezone.utc).isoformat(),
                  "input_file": str(args.input.resolve()),
                  "input_sha256": hashlib.sha256(input_bytes).hexdigest(),
                  "base_top_ties": [r["region_code"] for r in ranked if r["rank_base"] == 1],
                  "top_candidates": ranked[:5], "warnings": warnings}
        (args.output / "selection_review.json").write_text(
            json.dumps(review, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        if args.synthetic:
            print("가상 자료 검증 실행 — 실제 지역 선정 결과가 아닙니다.")
        print(f"완료: {len(ranked)}개 지역 비교. 결과: {args.output.resolve()}")
        print("개발자 최종 검토 필요. 반려견 동반 시설 부족을 입증하는 결과가 아닙니다.")
    except (ValueError, OSError, csv.Error) as exc:
        parser.exit(2, f"입력/출력 오류: {exc}\n")


if __name__ == "__main__":
    main()
