"""공식 TourAPI 방문자 수 수집. Python 표준 라이브러리만 사용한다.

공식 명세: https://www.data.go.kr/data/15101972/openapi.do
숙박방문자 비율은 이 API에 없으므로 만들어 내거나 0으로 채우지 않는다.
"""
import argparse
import calendar
import csv
import hashlib
import http.client
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

if __package__:
    from .select_development_region import months_between
else:
    from select_development_region import months_between

BASE_URL = "https://apis.data.go.kr/B551011/DataLabService"
OPERATIONS = {"sido": "metcoRegnVisitrDDList", "sigungu": "locgoRegnVisitrDDList"}
SOURCE_URL = "https://www.data.go.kr/data/15101972/openapi.do"
AUTH_CODES = {"20", "30", "31", "SERVICE_KEY_IS_NULL", "SERVICE_KEY_IS_NOT_REGISTERED_ERROR"}
RETRY_CODES = {"01", "04", "05", "23"}

# [지역 선정 기준 점검 2026-09-24: 실제 응답과 집계 열의 관계]
# 원문 위치: runs/api_candidates_{sido|sigungu}_202509_202608/raw/*.xml.
# baseYmd=기준일 YYYYMMDD, areaCode/areaNm=시도 코드/이름,
# signguCode/signguNm=시군구 코드/이름(시군구 응답),
# daywkDivCd/daywkDivNm=요일 코드/이름(현재 집계에서는 사용하지 않음),
# touDivCd/touDivNm=방문자 구분 코드/이름, touNum=해당 일자·지역·구분의 방문자 지표.
# 실제 구분값은 원문에서 확인한다. 지역 선정에는 touDivNm='외지인(b)'만 사용한다.
# header.resultCode/resultMsg=응답 상태, body.totalCount/pageNo/numOfRows=페이지 메타데이터.
# visitors는 일별 touNum의 월 합계다. 월간 순방문자나 반려견 동반 방문자 수로 해석하지 않는다.
# 숙박방문자 비율은 별도 다운로드 CSV에서 가져오며 이 API로 산출하지 않는다.


class ApiError(ValueError):
    def __init__(self, message, code="", retryable=False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 인증키가 포함된 요청을 다른 주소로 전달하지 않는다.
        return None


def load_key(env_name="TOURAPI_SERVICE_KEY", key_file=None, required=True):
    value = (os.environ.get(env_name) or "").strip()
    if key_file is not None:
        value = Path(key_file).read_text(encoding="utf-8-sig").strip()
    if not value and required:
        raise ApiError(f"인증키가 없습니다. {env_name} 환경변수 또는 --key-file로 설정하세요.", "missing_key")
    if any(char.isspace() for char in value):
        raise ApiError("인증키 안에 공백/줄바꿈이 있습니다. 한 줄의 키만 사용하세요.", "invalid_key")
    # 포털의 Encoding/Decoding 키를 모두 허용하되 URL 인코딩은 한 번만 한다.
    return urllib.parse.unquote(value)


def make_params(start, end, page, page_size):
    return {"MobileOS": "ETC", "MobileApp": "TogetherWithMyDog",
            "startYmd": start, "endYmd": end,
            "pageNo": page, "numOfRows": page_size}


def build_url(level, params, key):
    query = dict(params)
    if key:
        query["serviceKey"] = key
    return BASE_URL + "/" + OPERATIONS[level] + "?" + urllib.parse.urlencode(query)


def api_status(code):
    code = str(code)
    # 원문 에러 메시지/URL은 인증키를 포함할 수 있으므로 출력하지 않는다.
    if code in {"0000", "00", "0"}:
        return
    if code in AUTH_CODES:
        message = "인증키 또는 해당 API의 활용 승인 상태를 확인하세요."
    elif code == "22":
        message = "일일 호출 한도를 초과했습니다. 한도 초기화 후 새 실행으로 재시도하세요."
    else:
        message = "API 오류가 발생했습니다. 공식 명세의 오류코드를 확인하세요."
    safe_code = code if re.fullmatch(r"[A-Z0-9_]{1,80}", code) else "unknown"
    raise ApiError(f"{message} (코드 {safe_code})", safe_code, code in RETRY_CODES)


def parse_payload(payload):
    # JSON의 response.body.items.item 또는 XML의 body/items/item을 공통 dict 목록으로 변환.
    # 단일 JSON 객체도 리스트로 통일하고 정상 응답 코드·페이지 정보를 검사한다.
    # 항목의 지표를 합산하거나 결측을 채우는 함수가 아니다. 실제 합산은 summarize_month().
    try:
        text = payload.decode("utf-8-sig")
        if text.lstrip().startswith("{"):
            data = json.loads(text)
            response = data.get("response", data)
            header = response.get("header", {})
            api_status(header.get("resultCode", "missing_result_code"))
            body = response["body"]
            items = body.get("items") or {}
            records = items.get("item", []) if isinstance(items, dict) else items
            if isinstance(records, dict):
                records = [records]
        else:
            root = ET.fromstring(text)
            # 네임스페이스가 있는 XML도 같은 공식 필드명으로 처리한다.
            for element in root.iter():
                element.tag = element.tag.rsplit("}", 1)[-1]
            gateway_error = root.find(".//returnReasonCode")
            if gateway_error is not None:
                api_status(gateway_error.text or "unknown")
            api_status(root.findtext(".//header/resultCode", "missing_result_code"))
            body_element = root.find("body")
            if body_element is None:
                body_element = root.find(".//body")
            if body_element is None:
                raise ValueError("missing body")
            body = {name: body_element.findtext(name)
                    for name in ("totalCount", "pageNo", "numOfRows")}
            records = [{child.tag: child.text or "" for child in item}
                       for item in body_element.findall("./items/item")]
        total, page, size = (int(body[name]) for name in ("totalCount", "pageNo", "numOfRows"))
        if total < 0 or page < 1 or size < 0 or not isinstance(records, list):
            raise ValueError("invalid pagination")
        # 반려동물 API는 정상적인 0건 결과에 numOfRows=0을 반환한다.
        # 데이터가 있다고 표시된 응답의 0 크기 페이지는 계속 거부한다.
        if size == 0 and (total != 0 or records):
            raise ValueError("invalid empty pagination")
        if not all(isinstance(item, dict) for item in records):
            raise ValueError("invalid item")
        return records, total, page, size
    except ApiError:
        raise
    except (UnicodeError, ValueError, TypeError, KeyError, AttributeError, ET.ParseError):
        raise ApiError("API 응답 형식이 공식 XML/JSON 명세와 다릅니다.", "invalid_response") from None


class Client:
    def __init__(self, key, level, timeout=30, retries=2, interval=0.3):
        self.key, self.level = key, level
        self.timeout, self.retries, self.interval = timeout, retries, interval
        self.opener = urllib.request.build_opener(NoRedirect())
        self.request_count = 0

    def request(self, params):
        for attempt in range(self.retries + 1):
            if self.request_count:
                time.sleep(self.interval)
            self.request_count += 1
            try:
                request = urllib.request.Request(build_url(self.level, params, self.key),
                                                 headers={"User-Agent": "TogetherWithMyDog/1.0"})
                with self.opener.open(request, timeout=self.timeout) as response:
                    payload = response.read()
                parsed = parse_payload(payload)
                return payload, parsed
            except urllib.error.HTTPError as exc:
                status = exc.code
                try:
                    parse_payload(exc.read())
                except ApiError as api_exc:
                    if api_exc.code in AUTH_CODES:
                        raise api_exc from None
                finally:
                    exc.close()
                error = ApiError(f"공식 API가 HTTP {status}를 반환했습니다.",
                                 f"HTTP_{status}", status in {429, 500, 502, 503, 504})
            except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException):
                error = ApiError("공식 API 연결 실패: 네트워크/프록시/인증서 설정을 확인하세요.", "network_error", True)
            except ApiError as exc:
                error = exc
            if not error.retryable or attempt == self.retries:
                raise error from None
            time.sleep(min(2 ** attempt, 8))


def date_range(start, end):
    current = start
    while current <= end:
        yield current.strftime("%Y%m%d")
        current += timedelta(days=1)


def month_window(month):
    year, number = map(int, month.split("-"))
    return date(year, number, 1), date(year, number, calendar.monthrange(year, number)[1])


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path, rows, fields):
    with path.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def download_window(client, start, end, output, manifest, page_size=1000):
    """동일 기간의 모든 페이지를 수집하고 건수·중복·기간을 검증한다."""
    # --regions 필터는 이 다운로드에 적용되지 않는다. API 반환 지역 전체를 원문에 보존하고
    # summarize_month에서 선택 지역을 거른다. 따라서 원문 행 수와 분석용 행 수는 다르다.
    all_rows, known_keys, page_no, total_count = [], set(), 1, None
    files = []
    while True:
        params = make_params(start, end, page_no, page_size)
        payload, (rows, total, actual_page, actual_size) = client.request(params)
        if actual_page != page_no or (total_count is not None and total != total_count):
            raise ApiError("조회 중 페이지 번호/전체 건수가 바뀌었습니다. 새 결과 폴더로 재실행하세요.")
        total_count = total
        if len(rows) > actual_size or (not rows and len(all_rows) < total_count):
            raise ApiError("페이지가 비었거나 페이지 건수가 잘못되어 전체 수집을 확인할 수 없습니다.")
        for row in rows:
            code_field = "areaCode" if client.level == "sido" else "signguCode"
            key = (str(row.get(code_field, "")), str(row.get("baseYmd", "")), str(row.get("touDivCd", "")))
            if any(not value for value in key) or key in known_keys:
                raise ApiError("API의 지역+일자+방문자구분 키가 누락되었거나 중복되었습니다.")
            if not re.fullmatch(r"[0-9]{8}", key[1]) or not start <= key[1] <= end:
                raise ApiError("API 응답에 요청 기간 밖의 일자가 있습니다.")
            known_keys.add(key)
        # 원본은 요청 URL/인증키 없이 보관한다. 키를 반사하는 비정상 응답은 저장하지 않는다.
        if client.key and any(value.encode() in payload for value in
                              (client.key, urllib.parse.quote(client.key, safe=""))):
            raise ApiError("API 응답에 인증키가 포함되어 원본 저장을 중단했습니다.")
        extension = "json" if payload.lstrip().startswith(b"{") else "xml"
        relative = f"raw/{start}_{end}_p{page_no:04d}.{extension}"
        (output / relative).write_bytes(payload)
        manifest["pages"].append({"file": relative, "request": params,
                                  "rows": len(rows), "total_count": total,
                                  "sha256": hashlib.sha256(payload).hexdigest(),
                                  "downloaded_utc": datetime.now(timezone.utc).isoformat()})
        files.append(relative)
        all_rows.extend(rows)
        if len(all_rows) > total_count:
            raise ApiError("수집 건수가 API 전체 건수를 초과했습니다.")
        if len(all_rows) == total_count:
            break
        page_no += 1
        if page_no > 10000:
            raise ApiError("페이지 한도를 초과했습니다. 조회 범위를 줄여 확인하세요.")
    return all_rows, files


def summarize_month(rows, month, level, selected_codes, visitor_type, source_files):
    # 1) 방문자 유형과 지역코드를 필터링한다. sido는 areaCode, sigungu는 signguCode 사용.
    # 2) touNum을 Decimal로 읽고 음수/비유한수/같은 지역·일자의 중복을 거부한다.
    # 3) 달력의 모든 날짜가 정확히 있어야 월 합계를 만든다. 누락일을 0으로 대체하지 않는다.
    # 4) visitors=sum(일별 touNum), observed_days=해당 월 날짜 수, visitor_source=입력 페이지 목록.
    # 기존 2026-08 원문은 1~15일뿐이어서 fetch 전체 실행은 실패했고 월별 CSV도 쓰이지 않았다.
    # prepare_city_comparison은 보존된 원문에서 완전한 2025-09~2026-07만 다시 집계한다.
    code_field, name_field = (("areaCode", "areaNm") if level == "sido"
                              else ("signguCode", "signguNm"))
    daily = defaultdict(dict)
    names, type_codes = {}, set()
    for row in rows:
        if str(row.get("touDivNm", "")).strip() != visitor_type:
            continue
        code = str(row[code_field]).strip()
        if selected_codes and code not in selected_codes:
            continue
        name, day = str(row.get(name_field, "")).strip(), str(row["baseYmd"])
        if not code or not name or (code in names and names[code] != name):
            raise ApiError("API의 지역 코드/지역명이 누락되었거나 변경되었습니다.")
        try:
            value = Decimal(str(row["touNum"]))
        except (InvalidOperation, KeyError):
            raise ApiError("방문값을 숫자로 읽을 수 없습니다.") from None
        if not value.is_finite() or value < 0:
            raise ApiError("방문값은 유한한 0 이상 숫자여야 합니다.")
        if day in daily[code]:
            raise ApiError("같은 지역·일자의 선택 방문자 유형이 중복되었습니다.")
        daily[code][day], names[code] = value, name
        type_codes.add(str(row.get("touDivCd", "")))
    if len(type_codes) != 1 or not daily:
        available = sorted({str(row.get("touDivNm", "")) for row in rows})
        raise ApiError(f"선택한 방문자 유형/지역의 자료가 없거나 유형 코드가 일관되지 않습니다. 반환 유형: {available}")
    expected_days = set(date_range(*month_window(month)))
    result = []
    for code in sorted(selected_codes or daily):
        found = set(daily.get(code, {}))
        if found != expected_days:
            missing = sorted(expected_days - found)
            raise ApiError(f"{code} {month}: 일별 자료 불완전 (누락 {len(missing)}일, 예: {', '.join(missing[:5])}). 0으로 채우지 않습니다.")
        result.append({"region_code": code, "region_name": names[code], "region_level": level,
                       "month": month, "visitors": str(sum(daily[code].values(), Decimal(0))),
                       "visitor_source": ";".join(source_files), "visitor_type": visitor_type,
                       "visitor_type_code": next(iter(type_codes)), "observed_days": len(found)})
    return result


def parser_for_cli():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("check", "probe", "fetch"):
        item = sub.add_parser(command, help={"check": "연결/인증 확인", "probe": "하루 자료로 지역·유형 확인",
                                             "fetch": "공통 기간 방문자 수 수집"}[command])
        item.add_argument("--level", required=True, choices=OPERATIONS)
        item.add_argument("--output", required=True, type=Path, help="아직 없는 결과 폴더")
        item.add_argument("--key-file", type=Path)
        item.add_argument("--key-env", default="TOURAPI_SERVICE_KEY")
        item.add_argument("--timeout", type=float, default=30)
        item.add_argument("--retries", type=int, default=2)
        if command == "fetch":
            item.add_argument("--start", required=True, help="YYYY-MM")
            item.add_argument("--end", required=True, help="YYYY-MM")
            item.add_argument("--regions", nargs="+", help="API가 반환한 지역 코드. 생략하면 모두 수집")
            item.add_argument("--visitor-type", default="외지인(b)", help="probe로 확인한 외지인 유형명과 정확히 일치")
        else:
            item.add_argument("--date", required=True, help="YYYY-MM-DD")
    return parser


def main(argv=None):
    parser = parser_for_cli()
    args = parser.parse_args(argv)
    manifest, created = None, False
    try:
        if not 0 < args.timeout <= 120 or not 0 <= args.retries <= 5:
            raise ValueError("timeout은 0 초과 120 이하, retries는 0~5여야 합니다.")
        if args.command == "fetch":
            months = sorted(months_between(args.start, args.end))
        else:
            if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", args.date):
                raise ValueError("날짜 형식은 YYYY-MM-DD입니다.")
            day = date.fromisoformat(args.date).strftime("%Y%m%d")
        key = load_key(args.key_env, args.key_file, required=args.command != "check")
        client = Client(key, args.level, args.timeout, args.retries)
        args.output.mkdir(parents=True, exist_ok=False)
        created = True
        (args.output / "raw").mkdir()
        manifest = {"status": "running", "command": args.command, "source": SOURCE_URL,
                    "endpoint": BASE_URL + "/" + OPERATIONS[args.level], "level": args.level,
                    "started_utc": datetime.now(timezone.utc).isoformat(), "pages": [],
                    "authenticated_key_supplied": bool(key), "overnight_ratio_available": False}
        if args.command == "check":
            _, (rows, total, _, _) = client.request(make_params(day, day, 1, 1))
            manifest.update(status="connection_verified", date=args.date, response_total_count=total)
            print("공식 API 정상 응답 확인. 이 명령은 분석용 자료를 저장하지 않습니다.")
        elif args.command == "probe":
            rows, _ = download_window(client, day, day, args.output, manifest)
            if not rows:
                raise ApiError("조회일에 반환된 데이터가 없습니다. 제공 기간/갱신 시점을 확인하세요.")
            code_field, name_field = (("areaCode", "areaNm") if args.level == "sido"
                                      else ("signguCode", "signguNm"))
            regions = sorted({(str(row[code_field]), str(row[name_field])) for row in rows})
            write_csv(args.output / "available_regions.csv",
                      [{"region_code": code, "region_name": name} for code, name in regions],
                      ["region_code", "region_name"])
            types = sorted({(str(row["touDivCd"]), str(row["touDivNm"])) for row in rows})
            manifest.update(status="probe_complete", date=args.date,
                            visitor_types=[{"code": code, "name": name} for code, name in types],
                            region_count=len(regions))
            print(f"실제 응답 확인: 지역 {len(regions)}개. available_regions.csv와 manifest.json을 확인하세요.")
        else:
            manifest.update(period=[args.start, args.end], requested_regions=args.regions,
                            visitor_type=args.visitor_type,
                            aggregation="sum daily visitors within each calendar month",
                            data_lab_monthly_equivalence="requires source comparison")
            monthly, expected_regions, expected_names, expected_type_codes = [], None, None, None
            selected = set(args.regions or [])
            for month in months:
                start_date, end_date = month_window(month)
                raw, files = download_window(client, start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d"),
                                             args.output, manifest)
                summary = summarize_month(raw, month, args.level, selected, args.visitor_type, files)
                current_regions = {row["region_code"] for row in summary}
                current_names = {row["region_code"]: row["region_name"] for row in summary}
                current_types = {row["visitor_type_code"] for row in summary}
                if expected_regions is not None and (current_regions != expected_regions or
                        current_names != expected_names or current_types != expected_type_codes):
                    raise ApiError("기간 중 지역 목록/이름/방문자 유형 코드가 달라졌습니다. 동일 경계·유형으로 재확인하세요.")
                expected_regions, expected_names, expected_type_codes = current_regions, current_names, current_types
                monthly.extend(summary)
                print(f"{month}: {len(summary)}개 지역의 모든 일자 확인")
                write_json(args.output / "manifest.json", manifest)
            write_csv(args.output / "visitors_monthly.csv", monthly, list(monthly[0]))
            manifest.update(status="visitors_complete_overnight_required", region_count=len(expected_regions),
                            monthly_row_count=len(monthly), completed_months=len(months),
                            output_sha256=hashlib.sha256((args.output / "visitors_monthly.csv").read_bytes()).hexdigest())
            print("방문자 수 월별 집계 완료. 숙박비율을 확보·결합하기 전에는 지역 점수를 계산할 수 없습니다.")
        manifest.update(request_count=client.request_count, finished_utc=datetime.now(timezone.utc).isoformat())
        write_json(args.output / "manifest.json", manifest)
        return 0
    except (ApiError, ValueError, OSError, KeyError) as exc:
        if isinstance(exc, ApiError):
            message, code = str(exc), exc.code
        elif isinstance(exc, OSError):
            message, code = "로컬 파일/폴더를 읽거나 쓸 수 없습니다. 경로·권한·기존 결과 폴더를 확인하세요.", "file_error"
        elif isinstance(exc, KeyError):
            message, code = "API에 필수 응답 필드가 없습니다.", "missing_field"
        else:
            message, code = str(exc), "invalid_input"
        if created and manifest is not None:
            manifest.update(status="authentication_required" if code in AUTH_CODES else "failed",
                            error_code=code, error=message, request_count=client.request_count,
                            finished_utc=datetime.now(timezone.utc).isoformat())
            try:
                write_json(args.output / "manifest.json", manifest)
            except OSError:
                pass
        print(f"중단: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
