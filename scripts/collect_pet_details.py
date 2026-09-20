import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from app.integrations.tourapi_client import pet_detail
from Together_with_my_dog_cityselection.fetch_tourapi import ApiError


def main():
    parser = argparse.ArgumentParser(description="장소별 TourAPI 동반 상세 원문 보관. 규정을 자동 승인하지 않습니다.")
    parser.add_argument("content_ids", nargs="+")
    parser.add_argument("--key-file", default=".secrets/pet_tourapi.key")
    parser.add_argument("--operation", default="detailPetTour2", help="현재 승인받은 TourAPI 명세의 operation")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if any(not re.fullmatch(r"[0-9]+", x) for x in args.content_ids):
        parser.error("contentId는 숫자여야 합니다.")
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        for content_id in dict.fromkeys(args.content_ids):
            payload, records = pet_detail(content_id, args.key_file, args.operation)
            ext = "json" if payload.lstrip().startswith(b"{") else "xml"
            (args.output / f"{content_id}.{ext}").write_bytes(payload)
            (args.output / f"{content_id}_review.json").write_text(json.dumps({
                "content_id": content_id, "collected_at": datetime.now(timezone.utc).isoformat(),
                "review_status": "unreviewed", "records": records,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
    except ApiError as exc:
        parser.exit(1, f"{exc}\n")
    print("상세 원문 수집 완료. 마릿수·체중·객실/프로그램별 규정을 확인한 뒤 curated 자료에 반영하세요.")


if __name__ == "__main__":
    main()
