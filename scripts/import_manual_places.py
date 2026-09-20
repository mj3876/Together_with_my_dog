"""Produce a review template/schema or import reviewed records; never fabricate approval."""
import argparse
import csv
import json
from pathlib import Path
from app.schemas.place import Place
from scripts.build_service_db import import_catalog
from app.core.config import Settings


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)


def from_tourapi(path):
    result = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if not row.get("addr1", "").startswith(("대전 ", "대전광역시 ")):
                continue
            category = {"32":"lodging", "39":"restaurant"}.get(row["content_type_id"])
            if not category:
                continue
            place = Place(id="tour_" + row["content_id"], venue_id="tour_" + row["content_id"],
                          name=row["title"], latitude=float(row["mapy"]), longitude=float(row["mapx"]),
                          address=row["addr1"] + " " + row.get("addr2", ""), category=category,
                          description="TourAPI 목록 후보. 실제 동반 규정·객실/프로그램·운영 정보 미검토.")
            result.append(place.model_dump(mode="json"))
    return result


def main():
    parser = argparse.ArgumentParser(description="검토용 자료 생성 또는 수동 검토 JSON 적재")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--from-tourapi", type=Path)
    group.add_argument("--schema", action="store_true")
    group.add_argument("--template", action="store_true")
    group.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--database")
    args = parser.parse_args()
    if args.input:
        print(f"{import_catalog([args.input], args.database or Settings.from_env().database_path)}개 적재")
        return
    if args.output is None:
        parser.error("자료 생성에는 --output이 필요합니다. 기존 파일은 덮어쓰지 않습니다.")
    if args.schema:
        data = Place.model_json_schema()
    elif args.from_tourapi:
        data = from_tourapi(args.from_tourapi)
    else:
        # Deliberately incomplete and inactive. Import requires real location values.
        data = [{"id":"replace_with_id", "venue_id":"replace_with_venue_id", "category":"activity",
                 "name":"실제 업체명으로 교체", "address":"대전광역시 실제 주소로 교체", "latitude":None,
                 "longitude":None, "active":False, "product_name":"실제 프로그램명으로 교체",
                 "recurring":False, "duration_minutes":None, "policy":{"verified":False,
                 "pet_allowed":False, "max_dogs":None, "max_weight_kg":None, "source_url":None,
                 "source_quote":"", "checked_at":None, "requirements":[]}}]
    write_new(args.output, data)
    print(f"검토 자료 생성: {args.output}. active=false 상태이며 자동 추천에 사용되지 않습니다.")


if __name__ == "__main__":
    main()
