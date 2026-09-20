"""한국관광공사 반려동물 동반여행 서비스 목록 수집기.

기본값은 TourAPI의 KorPetTourService2/areaBasedList2 목록 API를 사용한다.
API 원문 응답은 raw 폴더에 보존하고, 집계에 필요한 공통 필드는 places.csv로
정리한다. 인증키는 명령행에 직접 쓰지 않고 --key-file 또는 환경변수로 받는다.
"""
import argparse
import csv
import hashlib
import http.client
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from .fetch_tourapi import ApiError, NoRedirect, load_key, parse_payload
else:
    from fetch_tourapi import ApiError, NoRedirect, load_key, parse_payload


DEFAULT_BASE_URL = "https://apis.data.go.kr/B551011/KorPetTourService2"
DEFAULT_OPERATION = "areaBasedList2"
SOURCE_URL = "https://api.visitkorea.or.kr/"
SERVICE_NAME = "한국관광공사_반려동물_동반여행_서비스"
DEFAULT_AREA_CODES = ["2", "3", "6", "32", "37"]
DEFAULT_CONTENT_TYPE_IDS = ["32", "39"]
PLACE_FIELDS = [
    "content_id", "content_type_id", "title", "addr1", "addr2",
    "area_code", "sigungu_code", "mapx", "mapy", "query_area_code",
    "query_content_type_id", "source_file",
]


def field_value(row, *names):
    values = {"".join(ch for ch in str(key).lower() if ch.isalnum()): value
              for key, value in row.items()}
    for name in names:
        value = values.get("".join(ch for ch in name.lower() if ch.isalnum()), "")
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def normalise_place(row, *, query_area_code, query_content_type_id, source_file):
    return {
        "content_id": field_value(row, "content_id", "contentid"),
        "content_type_id": field_value(row, "content_type_id", "contenttypeid") or query_content_type_id,
        "title": field_value(row, "title", "name"),
        "addr1": field_value(row, "addr1", "address", "address1"),
        "addr2": field_value(row, "addr2", "address2"),
        "area_code": field_value(row, "area_code", "areacode"),
        "sigungu_code": field_value(row, "sigungu_code", "sigungucode", "signgucode"),
        "mapx": field_value(row, "mapx", "longitude"),
        "mapy": field_value(row, "mapy", "latitude"),
        "query_area_code": query_area_code,
        "query_content_type_id": query_content_type_id,
        "source_file": source_file,
    }


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_url(base_url, operation, params, key):
    query = dict(params)
    query["serviceKey"] = key
    return f"{base_url.rstrip('/')}/{operation}?{urllib.parse.urlencode(query)}"


class PetClient:
    def __init__(self, key, base_url, operation, timeout=30, retries=2, interval=0.3):
        self.key = key
        self.base_url = base_url
        self.operation = operation
        self.timeout = timeout
        self.retries = retries
        self.interval = interval
        self.request_count = 0
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, params):
        error = None
        for attempt in range(self.retries + 1):
            if self.request_count:
                time.sleep(self.interval)
            self.request_count += 1
            try:
                request = urllib.request.Request(
                    build_url(self.base_url, self.operation, params, self.key),
                    headers={"User-Agent": "TogetherWithMyDog/1.0"},
                )
                with self.opener.open(request, timeout=self.timeout) as response:
                    payload = response.read()
                return payload, parse_payload(payload)
            except urllib.error.HTTPError as exc:
                status = exc.code
                try:
                    parse_payload(exc.read())
                except ApiError as api_error:
                    raise api_error from None
                finally:
                    exc.close()
                error = ApiError(f"반려동물 API가 HTTP {status}를 반환했습니다.",
                                 f"HTTP_{status}", status in {429, 500, 502, 503, 504})
            except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException):
                error = ApiError("반려동물 API 연결 실패. 네트워크·인증키·접근 권한을 확인하세요.",
                                 "network_error", True)
            except ApiError as api_error:
                error = api_error
            if not error.retryable or attempt == self.retries:
                raise error from None
            time.sleep(min(2 ** attempt, 8))


def make_params(area_code, content_type_id, page, page_size):
    params = {
        "MobileOS": "ETC",
        "MobileApp": "TogetherWithMyDog",
        "_type": "json",
        "areaCode": area_code,
        "pageNo": page,
        "numOfRows": page_size,
    }
    if content_type_id:
        params["contentTypeId"] = content_type_id
    return params


def fetch_query(client, output, query_number, area_code, content_type_id, page_size, manifest):
    all_rows = []
    page = 1
    total_count = None
    query_files = []
    while True:
        params = make_params(area_code, content_type_id, page, page_size)
        payload, (rows, total, actual_page, actual_size) = client.request(params)
        if actual_page != page or (total_count is not None and total != total_count):
            raise ApiError("페이지 번호 또는 전체 건수가 응답 중 변경되었습니다.", "pagination_changed")
        total_count = total
        if len(rows) > actual_size or (not rows and len(all_rows) < total_count):
            raise ApiError("API 페이지 건수가 명세와 다릅니다.", "invalid_pagination")
        extension = "json" if payload.lstrip().startswith(b"{") else "xml"
        relative = Path("raw") / f"q{query_number:02d}_p{page:04d}.{extension}"
        path = output / relative
        path.write_bytes(payload)
        query_files.append(relative.as_posix())
        manifest["pages"].append({
            "file": relative.as_posix(),
            "request": params,
            "rows": len(rows),
            "total_count": total,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "downloaded_utc": datetime.now(timezone.utc).isoformat(),
        })
        all_rows.extend(rows)
        if len(all_rows) > total_count:
            raise ApiError("수집 건수가 API 전체 건수를 초과했습니다.", "pagination_overflow")
        if len(all_rows) == total_count:
            break
        page += 1
        if page > 10000:
            raise ApiError("페이지 반복 횟수를 초과했습니다.", "pagination_limit")
    manifest["queries"].append({
        "area_code": area_code,
        "content_type_id": content_type_id,
        "total_count": total_count,
        "rows_collected": len(all_rows),
        "files": query_files,
    })
    return [normalise_place(row, query_area_code=area_code,
                             query_content_type_id=content_type_id,
                             source_file=";".join(query_files))
            for row in all_rows]


def add_arguments(parser, *, check=False):
    parser.add_argument("--key-file", type=Path, help="인증키 한 줄을 담은 파일")
    parser.add_argument("--key-env", default="TOURAPI_SERVICE_KEY")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--operation", default=DEFAULT_OPERATION)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--interval", type=float, default=0.3)
    if check:
        parser.add_argument("--area-code", default="3")
        parser.add_argument("--content-type-id", default="32")
    else:
        parser.add_argument("--area-codes", nargs="+", default=DEFAULT_AREA_CODES)
        parser.add_argument("--content-type-ids", nargs="+", default=DEFAULT_CONTENT_TYPE_IDS)
        parser.add_argument("--page-size", type=int, default=1000)
        parser.add_argument("--output", required=True, type=Path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check_parser = subparsers.add_parser("check", help="반려동물 API 권한과 응답을 한 번 확인")
    add_arguments(check_parser, check=True)
    fetch_parser = subparsers.add_parser("fetch", help="지역·업종별 목록 전체 수집")
    add_arguments(fetch_parser)
    args = parser.parse_args(argv)
    try:
        if not 0 < args.timeout <= 120 or not 0 <= args.retries <= 5 or not 0 <= args.interval <= 10:
            raise ValueError("timeout/retries/interval 범위를 확인하세요.")
        key = load_key(args.key_env, args.key_file, required=True)
        client = PetClient(key, args.base_url, args.operation, args.timeout, args.retries, args.interval)
        if args.command == "check":
            _, (_, total, _, _) = client.request(
                make_params(args.area_code, args.content_type_id, 1, 1))
            print(json.dumps({"status": "connection_verified", "service": SERVICE_NAME,
                              "response_total_count": total, "request_count": client.request_count},
                             ensure_ascii=False, indent=2))
            return
        if not args.area_codes or not args.content_type_ids:
            raise ValueError("area-code와 content-type-id가 하나 이상 필요합니다.")
        if not 0 < args.page_size <= 1000:
            raise ValueError("page-size는 1~1000이어야 합니다.")
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / "raw").mkdir()
        manifest = {
            "status": "running",
            "service": SERVICE_NAME,
            "source": SOURCE_URL,
            "base_url": args.base_url,
            "operation": args.operation,
            "area_codes": args.area_codes,
            "content_type_ids": args.content_type_ids,
            "page_size": args.page_size,
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "pages": [],
            "queries": [],
            "authenticated_key_supplied": True,
        }
        places = []
        query_number = 0
        for area_code in args.area_codes:
            for content_type_id in args.content_type_ids:
                query_number += 1
                places.extend(fetch_query(client, args.output, query_number, str(area_code),
                                           str(content_type_id), args.page_size, manifest))
                manifest["completed_queries"] = query_number
                write_json(args.output / "manifest.json", manifest)
        write_csv(args.output / "places.csv", places, PLACE_FIELDS)
        manifest.update({
            "status": "complete",
            "completed_utc": datetime.now(timezone.utc).isoformat(),
            "request_count": client.request_count,
            "raw_row_count": len(places),
            "rows_without_content_id": sum(not row["content_id"] for row in places),
            "places_sha256": hashlib.sha256((args.output / "places.csv").read_bytes()).hexdigest(),
        })
        write_json(args.output / "manifest.json", manifest)
        print(f"완료: {len(places)}건 수집. 결과: {args.output.resolve()}")
    except (ApiError, ValueError, OSError, csv.Error) as exc:
        parser.exit(2, f"수집 오류: {exc}\n")


if __name__ == "__main__":
    main()
