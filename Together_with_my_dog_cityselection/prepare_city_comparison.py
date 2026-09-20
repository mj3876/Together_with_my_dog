"""사용자가 제공한 실제 숙박 CSV와 시 전체 API 원본을 월별로 결합한다."""
import csv
import hashlib
import io
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

if __package__:
    from .fetch_tourapi import ApiError, parse_payload, summarize_month
    from .select_development_region import FIELDS, months_between
else:
    from fetch_tourapi import ApiError, parse_payload, summarize_month
    from select_development_region import FIELDS, months_between


CANDIDATES = {
    "대전광역시": ("30", "sido"),
    "인천광역시": ("28", "sido"),
    "부산광역시": ("26", "sido"),
    "강릉시": ("51150", "sigungu"),
    "전주시": ("52110", "sigungu"),
}
START, END = "2025-09", "2026-07"
MONTHS = months_between(START, END, expected_count=11)
OUTPUT = Path("data/processed/city_202509_202607")
API_SOURCE_PERIODS = ("202509_202607", "202509_202608")


def find_api_folder(level):
    for period in API_SOURCE_PERIODS:
        folder = Path(f"runs/api_candidates_{level}_{period}")
        if folder.exists():
            return folder
    raise FileNotFoundError(f"방문자 API 원본 폴더가 없습니다: {level}")


API_FOLDERS = {level: find_api_folder(level) for level in ("sido", "sigungu")}


def write_csv(path, rows, fields):
    with path.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    overnight, sources = {}, []
    for path in sorted(Path("data/raw").glob("*숙박방문자 비율 추이(외지인).csv")):
        raw = path.read_bytes()
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
        candidate_rows = [row for row in rows if row["지역명"] in CANDIDATES]
        if not candidate_rows:
            continue
        names = {row["지역명"] for row in candidate_rows}
        if len(names) != 1:
            raise ValueError(f"한 원본 파일에 여러 후보가 있습니다: {path.name}")
        name = names.pop()
        code, level = CANDIDATES[name]
        expected_baseline = "전국 광역지자체별 평균" if level == "sido" else "전국 기초지자체별 평균"
        if {row["지역명"] for row in rows} != {name, expected_baseline}:
            raise ValueError(f"지역 범위 확인 필요: {path.name}")
        found_months = set()
        used_rows = 0
        excluded_rows = 0
        for row in candidate_rows:
            raw_month = row["기준연월"]
            month = raw_month[:4] + "-" + raw_month[4:]
            if month not in MONTHS:
                excluded_rows += 1
                continue
            value = Decimal(row["숙박방문자 비율"])
            if not value.is_finite() or not 0 <= value <= 100:
                raise ValueError(f"숙박비율 또는 기간 확인 필요: {path.name}")
            if (code, month) in overnight:
                raise ValueError(f"중복 숙박자료: {name} {month}")
            overnight[code, month] = (str(value), path.as_posix())
            found_months.add(month)
            used_rows += 1
        if found_months != MONTHS:
            raise ValueError(f"숙박자료 11개월 누락: {name}")
        sources.append({"file": path.as_posix(), "region_name": name, "region_code": code,
                        "region_level": level, "sha256": hashlib.sha256(raw).hexdigest(),
                        "rows_used": used_rows, "excluded_period_rows": excluded_rows,
                        "national_average_rows_excluded": len(rows) - len(candidate_rows)})
    if len(overnight) != len(CANDIDATES) * len(MONTHS):
        raise ValueError("다섯 시의 숙박자료 55개를 확보해야 합니다.")

    visits, coverage = {}, []
    for level, folder in API_FOLDERS.items():
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        if manifest["status"] == "running":
            raise ValueError(f"API 수집이 아직 진행 중입니다: {level}")
        month_rows, month_files = defaultdict(list), defaultdict(list)
        for page in manifest["pages"]:
            path = folder / page["file"]
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != page["sha256"]:
                raise ValueError(f"수집 당시 원본 해시와 다릅니다: {path}")
            rows, *_ = parse_payload(raw)
            start = page["request"]["startYmd"]
            month = start[:4] + "-" + start[4:6]
            month_rows[month].extend(rows)
            month_files[month].append(path.as_posix())
        code_field = "areaCode" if level == "sido" else "signguCode"
        for name, (code, source_level) in CANDIDATES.items():
            if source_level != level:
                continue
            for month in sorted(MONTHS):
                selected_rows = [row for row in month_rows[month]
                                 if str(row[code_field]) == code and row["touDivNm"] == "외지인(b)"]
                observed = sorted({row["baseYmd"] for row in selected_rows})
                check = {"region_name": name, "region_code": code, "month": month,
                         "observed_days": len(observed), "first_day": observed[0] if observed else None,
                         "last_day": observed[-1] if observed else None}
                try:
                    summary = summarize_month(month_rows[month], month, level, {code}, "외지인(b)", month_files[month])
                    if len(summary) != 1 or summary[0]["region_name"] != name:
                        raise ValueError("지역명·코드 불일치")
                    visits[code, month] = summary[0]
                    check["status"] = "complete"
                except (ApiError, ValueError) as error:
                    check.update(status="incomplete", detail=str(error))
                coverage.append(check)

    combined = []
    for name, (code, level) in CANDIDATES.items():
        for month in sorted(MONTHS):
            overnight_value, overnight_file = overnight[code, month]
            visit = visits.get((code, month))
            combined.append({"region_code": code, "region_name": name, "region_level": level,
                             "month": month, "visitors": visit["visitors"] if visit else "",
                             "overnight_pct": overnight_value,
                             "visitor_source": visit["visitor_source"] if visit else "",
                             "overnight_source": overnight_file})
    OUTPUT.mkdir(parents=True, exist_ok=False)
    write_csv(OUTPUT / "region_monthly.csv", combined, FIELDS)
    write_csv(OUTPUT / "visitor_coverage.csv", coverage,
              ["region_name", "region_code", "month", "observed_days", "first_day", "last_day", "status", "detail"])
    missing = [row for row in coverage if row["status"] != "complete"]
    audit = {"period": [START, END], "analysis_month_count": len(MONTHS),
             "excluded_months": ["2026-08"], "comparison_scope": "whole_city",
             "candidate_count": len(CANDIDATES), "overnight_months": len(overnight),
             "complete_visitor_months": len(visits), "can_run_selection": not missing,
             "missing_visitor_months": missing, "overnight_sources": sources,
             "visitor_api_sources": {level: folder.as_posix() for level, folder in API_FOLDERS.items()},
             "input_sha256": hashlib.sha256((OUTPUT / "region_monthly.csv").read_bytes()).hexdigest()}
    (OUTPUT / "source_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    prior = Path("region_monthly.csv")
    if prior.exists():
        (OUTPUT / "previous_region_monthly.csv").write_bytes(prior.read_bytes())
    prior.write_bytes((OUTPUT / "region_monthly.csv").read_bytes())
    print(json.dumps({"overnight_months": len(overnight), "complete_visitor_months": len(visits),
                      "can_run_selection": not missing, "missing_visitor_months": missing}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
