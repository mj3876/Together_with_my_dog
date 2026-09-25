"""실제 API 수집 파일에서 방문자 집계 결과와 숙박비율 입력 대기 파일을 만든다."""
import argparse
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, fields):
    with path.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--sido", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads((args.input / "manifest.json").read_text(encoding="utf-8"))
    if manifest["status"] != "visitors_complete_overnight_required":
        raise SystemExit("실제 12개월 수집이 완료된 폴더가 필요합니다.")
    monthly_path = args.input / "visitors_monthly.csv"
    if hashlib.sha256(monthly_path.read_bytes()).hexdigest() != manifest["output_sha256"]:
        raise SystemExit("수집 당시의 월별 파일 해시와 다릅니다.")
    monthly = read_csv(monthly_path)
    provinces = {row["region_code"]: row["region_name"] for row in read_csv(args.sido)}
    groups = {}
    for row in monthly:
        groups.setdefault(row["region_code"], []).append(row)
    excluded, summary = [], []
    for code, records in groups.items():
        name = records[0]["region_name"]
        parent = groups.get(code[:-1] + "0") if not code.endswith("0") else None
        if parent and name.startswith(parent[0]["region_name"] + " "):
            excluded.append({"region_code": code, "region_name": name,
                             "parent_code": code[:-1] + "0",
                             "reason": "동시에 반환된 상위 시와 범위가 겹치는 일반구"})
            continue
        annual = sum((Decimal(row["visitors"]) for row in records), Decimal(0))
        peak = max(records, key=lambda row: Decimal(row["visitors"]))
        low = min(records, key=lambda row: Decimal(row["visitors"]))
        province = provinces.get(code[:2], "")
        summary.append({"region_code": code, "region_name": name, "sido_name": province,
                        "annual_daily_visitors_sum": annual,
                        "mean_monthly_visitors": annual / len(records),
                        "peak_month": peak["month"], "peak_month_visitors": peak["visitors"],
                        "low_month": low["month"], "low_month_visitors": low["visitors"],
                        "observed_months": len(records),
                        "observed_days": sum(int(row["observed_days"]) for row in records)})
    summary.sort(key=lambda row: (-row["annual_daily_visitors_sum"], row["region_code"]))
    for row in summary:
        row["visitor_volume_rank"] = 1 + sum(
            other["annual_daily_visitors_sum"] > row["annual_daily_visitors_sum"] for other in summary)
    args.output.mkdir(parents=True, exist_ok=False)
    write_csv(args.output / "visitor_volume_ranking.csv", summary, list(summary[0]))
    write_csv(args.output / "excluded_overlapping_districts.csv", excluded,
              ["region_code", "region_name", "parent_code", "reason"])
    included = {row["region_code"] for row in summary}
    pending = []
    for row in monthly:
        if row["region_code"] not in included:
            continue
        pending.append({"region_code": row["region_code"], "region_name": row["region_name"],
                        "region_level": "sigungu", "month": row["month"],
                        "visitors": row["visitors"], "overnight_pct": "",
                        "visitor_source": ";".join((args.input / part).as_posix()
                                                   for part in row["visitor_source"].split(";")),
                        "overnight_source": ""})
    write_csv(args.output / "region_monthly_pending_overnight.csv", pending, list(pending[0]))
    period_label = f"{manifest['period'][0]}~{manifest['period'][1]}"
    report = [f"# {period_label} 실제 방문자 데이터 집계", "",
              f"실제 API로 {len(groups)}개 지역 코드의 12개월 외지인(b) 자료를 수집했습니다. "
              f"원자료 {sum(page['rows'] for page in manifest['pages']):,}건, "
              f"월별 집계 {len(monthly):,}행입니다.", "",
              f"상위 시와 동시에 반환된 일반구 {len(excluded)}개를 비교표에서 제외해 "
              f"시·군·자치구·행정시 등 {len(summary)}개 지역의 방문 규모를 비교했습니다. "
              "제외 내역은 `excluded_overlapping_districts.csv`에 기록했고, 원자료와 전체 월별 집계에는 보존했습니다.", "",
              "## 외지인 방문 규모 상위 10개 지역", "",
              "| 순위 | 시도 | 지역 | 일별 방문값 연간 합계 | 월평균 | 최대 월 |",
              "|---:|---|---|---:|---:|---|"]
    for row in summary[:10]:
        report.append(f"| {row['visitor_volume_rank']} | {row['sido_name']} | {row['region_name']} | "
                      f"{row['annual_daily_visitors_sum']:,.1f} | {row['mean_monthly_visitors']:,.1f} | {row['peak_month']} |")
    report += ["", "## 해석과 남은 입력", "",
               "방문값은 일별 방문자 지표를 월별·연간으로 합산한 값입니다. 같은 사람이 여러 날 방문하면 "
               "반복 집계되므로 연간 고유 방문자 수나 고유 관광객 수로 읽으면 안 됩니다. 표시는 소수 첫째 자리로 반올림했고 CSV에는 계산값을 저장했습니다.", "",
               "이 결과는 방문 규모 비교입니다. 숙박방문자 비율은 API에서 제공하지 않아 빈칸으로 남겼으며, "
               "숙박비율을 포함한 점수와 개발 지역 최종 선정은 아직 계산하지 않았습니다. "
               "실제 비교 후보도 개발 가능 범위를 고려해 정해야 합니다.", "",
               f"`region_monthly_pending_overnight.csv`에 {len(pending):,}행의 실제 방문값을 입력해 두었습니다. "
               "같은 기간·지역의 실제 숙박비율과 출처를 채운 뒤 최종 분석에 사용할 수 있습니다.", "",
               "출처: [한국관광공사 지역별 방문자수 API](https://www.data.go.kr/data/15101972/openapi.do). "
               f"원본·요청 조건·SHA-256은 `{args.input.as_posix()}/manifest.json`에 있습니다.", ""]
    print("\n".join(report))


if __name__ == "__main__":
    main()
