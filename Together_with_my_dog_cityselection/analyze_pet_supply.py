"""반려동물 동반 시설 공급과 관광수요를 결합해 지역 부족순위를 계산한다.

입력은 fetch_pet_tourapi.py의 결과 폴더, API 응답 JSON/XML 폴더 또는
contentid/contenttypeid/addr1 열을 가진 CSV다. 시설 수는 API에 등록된
콘텐츠의 현재 스냅샷이며, 실제 업소 전수조사나 영업상태 검증 결과가 아니다.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

if __package__:
    from .fetch_tourapi import ApiError, parse_payload
    from .select_development_region import months_between
else:
    from fetch_tourapi import ApiError, parse_payload
    from select_development_region import months_between


SERVICE_NAME = "한국관광공사_반려동물_동반여행_서비스"
DEFAULT_START = "2025-09"
DEFAULT_END = "2026-07"
DEFAULT_LODGING_TYPE_IDS = ["32"]
DEFAULT_RESTAURANT_TYPE_IDS = ["39"]

# [지역 선정 기준 점검 2026-09-24]
# 실입력: runs/pet_api_20260919_183904/places.csv 63행 + region_monthly.csv 55행.
# 실결과: runs/pet_supply_20260919_184024/. 63개 ID 중 39개는 후보 지역, 24개는 미분류.
# 함수·열별 주석과 실제 원문 추적은 outputs/region_review_20260924/지역선정_분석기준_점검.md 참고.

NORMALISED_PLACE_FIELDS = [
    "content_id", "content_type_id", "category", "region_code", "region_name",
    "classification_method", "title", "addr1", "addr2", "area_code",
    "sigungu_code", "source_file",
]
UNMATCHED_FIELDS = ["reason", "content_id", "content_type_id", "title", "addr1",
                    "addr2", "area_code", "sigungu_code", "source_file"]
RANKING_FIELDS = [
    "shortage_rank", "region_code", "region_name", "region_level",
    "analysis_start", "analysis_end", "analysis_month_count",
    "mean_monthly_visitors", "pet_lodging_count", "pet_restaurant_count",
    "visitors_per_pet_lodging", "visitors_per_pet_restaurant",
    "lodging_shortage_percentile", "restaurant_shortage_percentile",
    "shortage_index", "lodging_status", "restaurant_status",
]


def normalise_key(value):
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def field_value(row, *names):
    values = {normalise_key(key): value for key, value in row.items()}
    for name in names:
        value = values.get(normalise_key(name), "")
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def normalise_text(value):
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text.replace("강원특별자치도", "강원도").replace("전북특별자치도", "전라북도")


def region_family(name):
    text = normalise_text(name)
    if "대전" in text:
        return "daejeon"
    if "인천" in text:
        return "incheon"
    if "부산" in text:
        return "busan"
    if "강릉" in text:
        return "gangneung"
    if "전주" in text:
        return "jeonju"
    return text


def classify_address(address, target_name):
    address = normalise_text(address)
    family = region_family(target_name)
    if not address:
        return False
    if family == "daejeon":
        return bool(re.search(r"(?:^|\s)(?:대전광역시|대전시)(?:\s|$)", address))
    if family == "incheon":
        return bool(re.search(r"(?:^|\s)(?:인천광역시|인천시)(?:\s|$)", address))
    if family == "busan":
        return bool(re.search(r"(?:^|\s)(?:부산광역시|부산시)(?:\s|$)", address))
    if family == "gangneung":
        return bool(re.search(r"(?:^|\s)강원도\s+강릉시(?:\s|$)", address)
                    or re.search(r"(?:^|\s)강릉시(?:\s|$)", address))
    if family == "jeonju":
        return bool(re.search(r"(?:^|\s)전라북도\s+전주시(?:\s|$)", address)
                    or re.search(r"(?:^|\s)전주시(?:\s|$)", address))
    target = normalise_text(target_name)
    return address.startswith(target) or bool(re.search(rf"(?:^|\s){re.escape(target)}(?:\s|$)", address))


def classify_place(place, demand_regions):
    # 주소(addr1+addr2)를 먼저 후보 도시와 대조한다. 강원/전북 전체 수집본에서 강릉/전주만 추린다.
    # 주소로 어느 후보도 매칭되지 않으면 area_code 2/3/6으로 광역시를 보완한다.
    # 실제 구현은 '주소가 빈 경우'에만 한정하지 않는다. 주소/코드 충돌 시 별도 검토가 필요하다.
    address = " ".join(filter(None, [place["addr1"], place["addr2"]]))
    for region in demand_regions:
        if classify_address(address, region["region_name"]):
            return region, "address"

    # 광역시는 주소가 비어도 TourAPI의 표준 areaCode로 보완할 수 있다.
    area_to_family = {"2": "incheon", "3": "daejeon", "6": "busan"}
    family = area_to_family.get(place["area_code"])
    if family:
        for region in demand_regions:
            if region_family(region["region_name"]) == family:
                return region, "area_code"
    return None, "unmatched_address"


def parse_number(value, label):
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        raise ValueError(f"{label}가 숫자가 아닙니다: {value!r}") from None
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{label}는 유한한 0 이상 숫자여야 합니다: {value!r}")
    return number


def load_demand(path, start, end):
    # 지역코드+월의 중복/누락, 11개월 공통기간, 숫자 범위를 검증한다.
    # mean_monthly_visitors = 11개 월별 visitors의 산술평균. overnight_pct는 여기서 사용하지 않는다.
    months = months_between(start, end, expected_count=11)
    required = {"region_code", "region_name", "region_level", "month", "visitors"}
    groups = defaultdict(dict)
    names, levels = {}, {}
    raw = path.read_bytes()
    with io.StringIO(raw.decode("utf-8-sig"), newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("수요 CSV 필수 열: " + ",".join(sorted(required)))
        for line, row in enumerate(reader, 2):
            if None in row:
                raise ValueError(f"수요 CSV {line}행의 열 개수가 맞지 않습니다.")
            code = field_value(row, "region_code")
            name = field_value(row, "region_name")
            level = field_value(row, "region_level")
            month = field_value(row, "month")
            if not all([code, name, level, month, field_value(row, "visitors")] ):
                raise ValueError(f"수요 CSV {line}행에 필수값이 누락되었습니다.")
            if month not in months:
                raise ValueError(f"수요 CSV {line}행의 월이 분석기간 밖입니다: {month}")
            value = parse_number(field_value(row, "visitors"), f"수요 CSV {line}행 방문자 지표")
            if code in names and names[code] != name:
                raise ValueError(f"수요 CSV 같은 지역코드의 지역명이 다릅니다: {code}")
            if code in levels and levels[code] != level:
                raise ValueError(f"수요 CSV 같은 지역코드의 행정단위가 다릅니다: {code}")
            if month in groups[code]:
                raise ValueError(f"수요 CSV 지역코드+월 중복: {code} {month}")
            names[code], levels[code] = name, level
            groups[code][month] = value
    if not groups:
        raise ValueError("수요 CSV에 지역 자료가 없습니다.")
    result = []
    for code in sorted(groups):
        missing = months - groups[code].keys()
        if missing:
            raise ValueError(f"수요 CSV {code} 누락 월: {', '.join(sorted(missing))}")
        result.append({
            "region_code": code,
            "region_name": names[code],
            "region_level": levels[code],
            "mean_monthly_visitors": mean(groups[code].values()),
            "analysis_month_count": len(months),
        })
    return result, hashlib.sha256(raw).hexdigest()


def normalise_place(row, source_file):
    # 원문 contentid/contenttypeid/areacode 등의 표기를 content_id/content_type_id/area_code로 통일.
    # fetch 결과 CSV도 같은 형태로 읽는다. 이 단계에서 좌표(mapx/mapy)는 집계에 쓰지 않아 제외한다.
    return {
        "content_id": field_value(row, "content_id", "contentid"),
        "content_type_id": field_value(row, "content_type_id", "contenttypeid",
                                        "query_content_type_id"),
        "title": field_value(row, "title", "name"),
        "addr1": field_value(row, "addr1", "address", "address1"),
        "addr2": field_value(row, "addr2", "address2"),
        "area_code": field_value(row, "area_code", "areacode"),
        "sigungu_code": field_value(row, "sigungu_code", "sigungucode", "signgucode"),
        "source_file": field_value(row, "source_file") or source_file,
    }


def csv_rows(path):
    raw = path.read_bytes()
    with io.StringIO(raw.decode("utf-8-sig"), newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        if not reader.fieldnames:
            raise ValueError(f"시설 CSV 헤더가 없습니다: {path}")
        for row in reader:
            if None in row:
                raise ValueError(f"시설 CSV 열 개수가 맞지 않습니다: {path}")
            yield normalise_place(row, path.as_posix())


def payload_rows(path):
    rows, _, _, _ = parse_payload(path.read_bytes())
    for row in rows:
        yield normalise_place(row, path.as_posix())


def input_files(path):
    # 결과 폴더에 places.csv가 있으면 그것만 읽는다(원문과 CSV를 동시에 합쳐 중복 집계하지 않음).
    # 원문 직접 분석 시에는 raw/ 또는 지정 폴더의 JSON/XML/CSV를 읽는다.
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise FileNotFoundError(f"시설 입력 경로가 없습니다: {path}")
    places = path / "places.csv"
    if places.exists():
        return [places]
    raw_dir = path / "raw"
    base = raw_dir if raw_dir.exists() else path
    files = sorted([*base.rglob("*.json"), *base.rglob("*.xml"), *base.rglob("*.csv")])
    if not files:
        raise FileNotFoundError(f"시설 CSV 또는 API 원문 응답이 없습니다: {path}")
    return files


def load_places(path):
    records = []
    files = input_files(path)
    for file in files:
        if file.suffix.lower() == ".csv":
            records.extend(csv_rows(file))
        else:
            try:
                records.extend(payload_rows(file))
            except (ApiError, ValueError) as exc:
                raise ValueError(f"시설 API 응답을 읽지 못했습니다: {file.name}: {exc}") from None
    return records, files


def quality(place):
    # content_id 중복 시 아래 5개 필드의 비어 있지 않은 수가 더 큰 행을 보존. 동점이면 첫 행 유지.
    # 이름/주소가 같은 서로 다른 content_id는 합치지 않으므로 실제 업소 단위 중복이 남을 수 있다.
    return sum(bool(place[key]) for key in ("content_type_id", "title", "addr1", "area_code", "sigungu_code"))


def percentile(values):
    # 후보 n곳 내 상대순위: (자신보다 작은 값의 수 + (동점 개수-1)/2)/(n-1).
    # 대전·전주 음식점 0개는 내부 부담도 inf로 공동 최댓값: (3+0.5)/4=0.875.
    n = len(values)
    if n < 2:
        raise ValueError("비교 지역은 2곳 이상 필요합니다.")
    return [(sum(x < value for x in values) + (sum(x == value for x in values) - 1) / 2)
            / (n - 1) for value in values]


def csv_number(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return round(value, 6)
    return value


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path,
                        help="fetch_pet_tourapi.py 결과 폴더 또는 시설 CSV/JSON/XML")
    parser.add_argument("--demand", default=Path("region_monthly.csv"), type=Path,
                        help="11개월 방문자 입력 CSV")
    parser.add_argument("--start", default=DEFAULT_START, help="YYYY-MM")
    parser.add_argument("--end", default=DEFAULT_END, help="YYYY-MM")
    parser.add_argument("--lodging-type-ids", nargs="+", default=DEFAULT_LODGING_TYPE_IDS,
                        help="숙박 콘텐츠 유형 코드. 기본 32")
    parser.add_argument("--restaurant-type-ids", nargs="+", default=DEFAULT_RESTAURANT_TYPE_IDS,
                        help="음식점 콘텐츠 유형 코드. 기본 39")
    parser.add_argument("--lodging-weight", type=float, default=0.5,
                        help="종합 부족지수에서 숙박 부담도가 차지하는 비중")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if not 0 <= args.lodging_weight <= 1:
            raise ValueError("lodging-weight는 0~1이어야 합니다.")
        demand, demand_sha256 = load_demand(args.demand, args.start, args.end)
        raw_places, source_files = load_places(args.input)
        lodging_ids = {str(value) for value in args.lodging_type_ids}
        restaurant_ids = {str(value) for value in args.restaurant_type_ids}
        selected_ids = lodging_ids | restaurant_ids
        category_by_type = {value: "lodging" for value in lodging_ids}
        category_by_type.update({value: "restaurant" for value in restaurant_ids})

        unmatched = []
        excluded_types = Counter()
        records_without_id = 0
        selected_rows = []
        for place in raw_places:
            if not place["content_id"]:
                records_without_id += 1
                unmatched.append({"reason": "missing_content_id", **place})
                continue
            type_id = place["content_type_id"]
            if type_id not in selected_ids:
                excluded_types[type_id or "missing"] += 1
                continue
            place["category"] = category_by_type[type_id]
            selected_rows.append(place)

        deduped = {}
        # content_id 하나당 한 건. 현 수집본은 63행/63개 ID로 제거된 중복은 0건이다.
        duplicate_rows_removed = 0
        category_conflict_ids = []
        for place in selected_rows:
            content_id = place["content_id"]
            if content_id in deduped:
                duplicate_rows_removed += 1
                if deduped[content_id]["category"] != place["category"]:
                    category_conflict_ids.append(content_id)
                if quality(place) > quality(deduped[content_id]):
                    deduped[content_id] = place
            else:
                deduped[content_id] = place

        classified = []
        counts = {region["region_code"]: {"lodging": 0, "restaurant": 0} for region in demand}
        for place in deduped.values():
            region, method = classify_place(place, demand)
            if region is None:
                unmatched.append({"reason": method, **place})
                continue
            place = {
                **place,
                "region_code": region["region_code"],
                "region_name": region["region_name"],
                "classification_method": method,
            }
            classified.append(place)
            counts[region["region_code"]][place["category"]] += 1

        lodging_burden = []
        # 부담도 = 월평균 일반 외지인 방문자 지표 / API 등록시설 수.
        # 시설 0개: 내부 계산은 inf, 결과 CSV의 비율은 빈칸, status는 no_registered_facility.
        # 실제 시설이 없다는 증거가 아니라 이 수집 범위에 등록된 건수가 0이라는 뜻이다.
        restaurant_burden = []
        for region in demand:
            item = counts[region["region_code"]]
            lodging_burden.append(math.inf if item["lodging"] == 0 else
                                  region["mean_monthly_visitors"] / item["lodging"])
            restaurant_burden.append(math.inf if item["restaurant"] == 0 else
                                     region["mean_monthly_visitors"] / item["restaurant"])
        lodging_pct = percentile(lodging_burden)
        restaurant_pct = percentile(restaurant_burden)
        ranking = []
        for i, region in enumerate(demand):
            item = counts[region["region_code"]]
            index = 100 * (args.lodging_weight * lodging_pct[i]
                           + (1 - args.lodging_weight) * restaurant_pct[i])
            # 기본 숙박/음식점 0.5씩. 대전은 100*(0.5*0.75+0.5*0.875)=81.25.
            # 절대적인 공급 부족률(%)이 아니라 다섯 후보 안의 상대 지수다.
            ranking.append({
                "region_code": region["region_code"],
                "region_name": region["region_name"],
                "region_level": region["region_level"],
                "analysis_start": args.start,
                "analysis_end": args.end,
                "analysis_month_count": region["analysis_month_count"],
                "mean_monthly_visitors": csv_number(region["mean_monthly_visitors"]),
                "pet_lodging_count": item["lodging"],
                "pet_restaurant_count": item["restaurant"],
                "visitors_per_pet_lodging": None if item["lodging"] == 0 else
                    csv_number(lodging_burden[i]),
                "visitors_per_pet_restaurant": None if item["restaurant"] == 0 else
                    csv_number(restaurant_burden[i]),
                "lodging_shortage_percentile": csv_number(lodging_pct[i]),
                "restaurant_shortage_percentile": csv_number(restaurant_pct[i]),
                "shortage_index": csv_number(index),
                "lodging_status": "no_registered_facility" if item["lodging"] == 0 else "registered_records",
                "restaurant_status": "no_registered_facility" if item["restaurant"] == 0 else "registered_records",
            })
        scores = [row["shortage_index"] for row in ranking]
        for row in ranking:
            row["shortage_rank"] = 1 + sum(score > row["shortage_index"] for score in scores)
        ranking.sort(key=lambda row: (-row["shortage_index"], row["region_code"]))

        args.output.mkdir(parents=True, exist_ok=False)
        write_csv(args.output / "pet_supply_ranking.csv", ranking, RANKING_FIELDS)
        write_csv(args.output / "pet_facilities_deduplicated.csv", classified,
                  NORMALISED_PLACE_FIELDS)
        write_csv(args.output / "unmatched_places.csv", unmatched, UNMATCHED_FIELDS)
        audit = {
            "status": "developer_review_required",
            "service": SERVICE_NAME,
            "analysis_period": [args.start, args.end],
            "analysis_month_count": 11,
            "demand_file": str(args.demand.resolve()),
            "demand_sha256": demand_sha256,
            "facility_input": str(args.input.resolve()),
            "source_files": [str(file.resolve()) for file in source_files],
            "source_file_count": len(source_files),
            "raw_record_count": len(raw_places),
            "selected_category_record_count": len(selected_rows),
            "unique_content_id_count": len(deduped),
            "duplicate_content_id_rows_removed": duplicate_rows_removed,
            "category_conflict_content_ids": sorted(set(category_conflict_ids)),
            "records_without_content_id": records_without_id,
            "classified_record_count": len(classified),
            "unmatched_record_count": len(unmatched),
            "unmatched_reasons": dict(Counter(row["reason"] for row in unmatched)),
            "excluded_content_type_counts": dict(excluded_types),
            "content_type_ids": {"lodging": sorted(lodging_ids),
                                 "restaurant": sorted(restaurant_ids)},
            "lodging_weight": args.lodging_weight,
            "ranking_definition": "higher shortage_index means more visitor demand per registered pet facility",
            "region_counts": counts,
            "warnings": [
                "시설 수는 API 등록 콘텐츠의 조회 시점 스냅샷이며 실제 업소 전수조사가 아닙니다.",
                "일반 방문자 지표를 반려견 동반 관광수요의 대리변수로 사용했습니다.",
                "시설 수가 0인 지역의 방문자/시설 비율은 n.a.로 표시하고 부족지수 계산에서는 가장 높은 부담으로 처리했습니다.",
                "콘텐츠 유형 코드는 TourAPI 서비스 명세와 대조한 뒤 확정해야 합니다.",
                "주소가 없거나 대상 지역으로 분류되지 않은 시설은 순위에서 제외하고 unmatched_places.csv에 기록했습니다.",
            ],
            "created_utc": datetime.now(timezone.utc).isoformat(),
        }
        (args.output / "pet_supply_audit.json").write_text(
            json.dumps(audit, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8")
        print(f"완료: {len(ranking)}개 지역 공급 부족순위 계산. 결과: {args.output.resolve()}")
    except (ApiError, ValueError, OSError, csv.Error) as exc:
        parser.exit(2, f"분석 오류: {exc}\n")


if __name__ == "__main__":
    main()
