# 실제 데이터 서비스 전환: 2인 작업 가이드

작성일: 2026-09-27. PowerShell 기준. 이 문서는 작업 분담·구현 명세·실행 순서이며, 문서 작성만으로 DB 이전이나 장소 활성화가 실행된 것은 아니다.

실행 후 업데이트: 이 가이드에 따라 정규화 적재기·조회 어댑터·점검기와 `--live` 실행 옵션을 구현하고 로컬 DB 이전을 수행했다. 아래의 “신규 구현 필요/구현 후” 표시는 최초 분담 계획이다. 현재 실제 결과·남은 조건·사용 명령은 [전환 작업 현황](live_transition_status.md)을 우선 참고한다. 활성 장소 확보와 카카오 키 입력은 아직 완료되지 않았다.

## 1. 역할과 작업 순서

**A는 실제 장소 조사와 검증 자료를 맡고, B는 DB 변경·앱 연결·카카오 API 설정을 맡는다. 실제 서비스 DB를 변경하는 담당자는 B 한 명으로 정한다.**

| 작업 | A — 데이터 담당 | B — 개발·연동 담당 | 완료 산출물 |
|---|---|---|---|
| 시작 | 기존 후보·규정 검토본 읽기 | 백업, 입력 스키마 공유 | 자료 양식·ID 규칙 합의 |
| 병행 1 | 숙소·식당·체험 실제 조건 조사 | 정규화 적재기·조회 어댑터 구현 | 검증 자료 / 코드 |
| 병행 2 | 주소·좌표·제한·소요시간 보완 | 카카오 키 설정·실제 호출 검사 | 근거 / API 검사 결과 |
| 1차 인계 | 검증 완료 자료와 미확인 목록 전달 | 시험 DB 적재·오류 목록 반환 | 자료별 승인·보류 사유 |
| 수정 | 데이터 오류·근거 부족 보완 | 어댑터·추천 필터 오류 수정 | 시험 적재 통과 |
| 전환 | 실제 정보와 화면 내용 대조 | DB 반영, 설정 전환, 서버 재시작 | 실제 모드 서비스 |
| 공동 검증 | 동반 조건·상품·표시 내용 확인 | 실제 추천·상세·경로·저장 확인 | 완료 기록 |

작업 의존성: B의 DB 구조·적재기 개발과 A의 조사는 동시에 진행한다. 최종 활성 데이터 적재는 A의 인계 후 진행한다. API 설정·호출 검사는 활성 데이터가 없어도 진행할 수 있다.

현재 기준: 실제 `app.db`에는 비활성 숙소 1건, 검토본에는 음식점 68곳과 비활성 상품/공간 9건이 있다. 후보 확보와 추천 활성화는 다른 단계다.

## 2. 공통 준비와 파일 소유권

각자 프로젝트 루트에서 실행한다. 다른 PC에서는 경로를 자신의 저장소 위치로 바꾼다.

```powershell
cd C:\Users\ms840\mjuser\Together_with_my_dog
# .venv가 없다면 먼저 실행
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r config/requirements.txt
```

| 담당 | 수정·생성할 파일 | 공유 방식 |
|---|---|---|
| A | `data/curated/approved_places.json`, `data/curated/pending_places.json`, `data/curated/review_handoff.md`, 공개 출처 근거 | 검증 JSON·근거를 B에게 파일로 전달 |
| B | `app/`, 적재·점검 스크립트, 필요한 스키마 마이그레이션 | 코드 변경으로 공유 |
| B | `data/app.db`, `data/app_normalized.db`, 백업, `.env` | B의 실행 환경에서 관리 |

`data/`, DB 파일, `.env`는 현재 Git 제외 대상이다. A의 자료는 커밋만으로 B에게 전달되지 않는다. 파일 전달을 별도로 진행하고, 키는 자료 인계에 포함하지 않는다. 같은 PC라면 A는 검토 자료만 편집하고 B가 DB를 변경한다.

## 3. A: 실제 장소 확보·검증

### A-1. 조사 시작 자료

- `outputs/policy_review_20260925/정책조사_검토본.md`
- `outputs/policy_review_20260925/restaurant_candidates.json`: 음식점 68곳
- `outputs/policy_review_20260925/policy_review.json`: 확인 내용·미확인 조건
- `outputs/policy_review_20260925/places_import_inactive.json`: 앱 호환 비활성 9건

1차 목표는 **숙소 1상품 + 서로 다른 식당 2곳 + 체험 2개**다. 이는 현재 2일 여행의 최소 후보 수이며, 같은 반려견 조건과 일정 조건을 충족해야 한다. 당일 여행의 최소 후보는 식당 1곳·체험 1개다. 조건 미충족이나 휴무 등을 고려해 후보를 더 확보하면 좋다.

### A-2. 검토 양식 생성 — 현재 실행 가능

아래 생성기는 기존 출력 파일이 있으면 덮어쓰지 않는다. 이미 생성했으면 기존 파일을 편집한다.

```powershell
.\.venv\Scripts\python.exe -m scripts.import_manual_places --schema --output data/curated/place_schema.json
.\.venv\Scripts\python.exe -m scripts.import_manual_places --template --output data/curated/new_place_review.json
```

생성된 양식은 미완성 비활성 예시다. 실제 자료를 입력하고 `approved_places.json`에 검증 완료 레코드만 배열로 모은다. 미확인 후보는 `pending_places.json` 및 인계 문서로 별도 전달한다. 현재 `Place`는 좌표가 필수이므로 좌표 미확인 후보를 억지로 그 양식에 맞추지 않는다.

### A-3. 장소마다 확인할 항목

| 구분 | 확인할 정보 |
|---|---|
| 공통 | 실제 업체명, 대전 주소, 정확한 위도·경도, 허용 공간, 공식/운영자 출처, 확인일 |
| 반려견 | 동반 허용, 일행 기준 최대 마릿수, 체중 상한, 미만/이하, 견종·체고·접종 등 필수 조건 |
| 숙소 | 동반 가능한 객실/독채 상품명, 체크인·아웃, 추가요금·준비물 |
| 식당 | 실제 식사 메뉴, 동반 가능한 식사 공간, 식사 시간 |
| 체험 | 실제 프로그램명, 운영 방식, 소요시간, 참가 대상·동반 범위·예약 조건 |

카카오 검색 결과는 주소·좌표 확인에 사용한다. 반려견 동반 규정을 확인한 근거로 대신 사용하지 않는다. 공식 웹 자료로 부족하면 운영자에게 확인하고 날짜·질문·답변·담당자 역할을 기록한다.

활성 JSON의 공통 필드는 `active=true`, `is_demo=false`, `policy.verified=true`, `policy.pet_allowed=true`다. 다음 필드도 근거와 함께 채운다.

- `policy.max_dogs` 또는 근거가 있는 `policy.dogs_unlimited=true`
- `policy.max_weight_kg`와 `weight_operator=lt/lte`, 또는 근거가 있는 `weight_unlimited=true`
- `policy.source_url`, `source_quote`, `checked_at`
- 숙소: `product_name`
- 식당: 실제 식사 제공 확인 후 `serves_meals=true`
- 체험: `product_name`, 운영 방식에 맞는 `recurring`, 실제 `duration_minutes`

모르는 제한을 무제한으로 입력하지 않는다. 체고를 체중으로 바꾸지 않는다. 현재 다섯 입력으로 판단할 수 없는 필수 조건이 있으면 보류 사유로 전달한다. 날짜별 회차만 있는 교육을 상시 체험으로 바꾸지 않는다. 현재 앱은 날짜 미지정 참고 계획이므로 실제 예약 확정을 표시하지 않는다.

ID는 상품·공간별로 구분하고 같은 업체는 `venue_id`를 공유한다. 기존 빨간대문 ID `tour_3533154`는 유지한다. 명부 행 번호를 영구 장소 ID로 사용하지 않는다.

### A-4. 형식 검증 — 실제 DB를 바꾸지 않음

```powershell
@'
import json
from collections import Counter
from pathlib import Path
from app.schemas.place import Place

rows = json.loads(Path('data/curated/approved_places.json').read_text(encoding='utf-8-sig'))
assert isinstance(rows, list) and rows, '비어 있지 않은 배열이 필요합니다.'
places = [Place.model_validate(row) for row in rows]
assert len({p.id for p in places}) == len(places), '중복 ID'
assert all(p.active and not p.is_demo and p.policy.verified and p.policy.pet_allowed for p in places)
print('형식 검사 통과:', dict(Counter(p.category for p in places)))
print('출처 내용 및 실제 규정의 검증은 별도로 필요합니다.')
'@ | .\.venv\Scripts\python.exe -X utf8 -
```

### A-5. B에게 전달

`approved_places.json`, 미확인 후보, 근거 파일, `review_handoff.md`를 전달한다. 인계 문서에는 카테고리별 건수, 각 상품의 제한, 미확인 필드, 확인일, 동일 업체/상품 ID 대응, 검증 기준으로 삼은 반려견 조건을 기록한다. A의 완료는 검증 자료 인계이고, 서비스 반영 완료는 B의 적재 결과로 확인한다.

## 4. B: 백업·기존 app.db 반영

### B-1. 백업 — 현재 실행 가능

실행 중인 서버 터미널에서 `Ctrl+C`로 종료한 뒤 실행한다.

```powershell
@'
import sqlite3
from pathlib import Path
from datetime import datetime

src = Path('data/app.db').resolve()
dst = src.with_name(f'app_backup_{datetime.now():%Y%m%d_%H%M%S_%f}.db')
with sqlite3.connect(src.as_uri() + '?mode=ro', uri=True) as source:
    with sqlite3.connect(dst) as backup:
        source.backup(backup)
print('백업 완료:', dst)
'@ | .\.venv\Scripts\python.exe -X utf8 -
```

### B-2. 검토 9건 반영 — 현재 실행 가능

```powershell
.\.venv\Scripts\python.exe -m scripts.build_service_db outputs/policy_review_20260925/places_import_inactive.json --database data/app.db
```

기존 동일 ID를 갱신하고 비활성 후보를 추가한다. **추천 가능한 장소가 늘어나는 명령은 아니다.** A의 승인 자료를 적재하기 전에 실행한다. 승인 자료를 반영한 뒤 이 오래된 검토본을 다시 적재하면 동일 ID가 비활성 상태로 덮어써질 수 있다.

### B-3. A의 자료 시험 적재 → 실제 반영

A에게 자료를 받은 뒤 실행한다. 시험 DB는 새 경로로 선택한다.

```powershell
$catalogCheckDb = 'data/catalog_check_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff') + '.db'
.\.venv\Scripts\python.exe -m scripts.build_service_db data/curated/approved_places.json --database $catalogCheckDb
if ($LASTEXITCODE -ne 0) { throw '시험 적재 실패: A에게 오류를 전달하세요.' }
```

형식 검사와 출처 검토가 완료되면 서버를 종료한 상태에서 실제 DB에 반영한다.

```powershell
.\.venv\Scripts\python.exe -m scripts.build_service_db data/curated/approved_places.json --database data/app.db
```

현재 적재기 통과는 전체 추천 조건 통과와 같지 않다. 식당 메뉴·체험 소요시간·입력으로 판정하지 못하는 필수 조건을 별도로 점검한다.

## 5. B: 정규화 DB 이전·앱 연결 구현

### B-4. 새 정규화 DB 생성 — 현재 실행 가능

현재 `docs/database_schema.sql`은 새 DB 전용이다. 기존 `app.db`에 직접 실행하지 않는다.

```powershell
@'
from pathlib import Path
import sqlite3

target = Path('data/app_normalized.db')
if target.exists():
    raise SystemExit('이미 존재하는 DB입니다. 초기화를 중단합니다.')
target.parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(target) as conn:
    conn.executescript(Path('docs/database_schema.sql').read_text(encoding='utf-8'))
    print('생성 테이블:', conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0])
'@ | .\.venv\Scripts\python.exe -X utf8 -
```

예상 결과는 22개 테이블이다. 아직 데이터가 들어가거나 앱이 연결된 것은 아니다.

### B-5. 코드 작업 명세 — 신규 구현 필요

| 파일 | 구현할 내용 |
|---|---|
| 신규 `scripts/migrate_service_db.py` | 기존 DB·조사 자료·A의 검증 자료를 읽어 출처, 장소, 상품, 정책 적재. `--dry-run` 지원 |
| 신규 `app/repositories/normalized_place_repository.py` | 정규화 테이블 조회 후 기존 `Place`로 변환 |
| `app/repositories/place_repository.py` | `all_places`, `get_place`를 설정된 저장소로 연결. 데모 쓰기는 기존 메모리 저장소에 한정 |
| `app/db/session.py` | 모든 정규화 연결에 외래키 활성화. 예상 스키마 검사. 잘못된 DB에 빈 `places` 테이블을 자동 생성하지 않기 |
| `app/core/config.py` | 신규 `DATABASE_BACKEND=legacy/normalized` 설정. 기본값과 오류 처리 명시 |
| `app/main.py` | 저장소 초기화 분기. 데모 분리. 상태 정보에 실제 저장소·카테고리별 후보 건수 표시 |
| 신규 `scripts/check_live_readiness.py` | 추천에 필요한 자료의 승인·보류 사유, DB 무결성, 설정 존재 여부를 검사. 키 값 출력 금지 |

정규화 매핑은 `venues.venue_id → Place.venue_id`, `offerings.offering_id → Place.id`다. `venues → offerings → 현행 pet_policy_versions`를 읽고 검증된 조건을 `Place`로 변환한다. 조회 함수의 호출부를 모두 확인해 추천·상세·교체·health가 같은 저장소를 사용하도록 한다.

적재 구현 순서:

1. 출처 → 수집 실행 → 파일·해시 → 원문 행을 저장한다.
2. 실제 장소·외부 ID를 적재한다. 음식점 등록 69건과 장소 68곳을 구분한다.
3. 객실·공간·프로그램을 상품 단위로 적재한다.
4. `policy_review.json`의 미확인 NULL을 보존한다. 앱 호환 비활성 파일의 false만 읽어 실제 금지로 해석하지 않는다.
5. A의 추가 검증 자료를 근거와 함께 반영한다. 기존 근거와 충돌하면 검토 이슈로 남긴다. 파일 순서만으로 검증 상태를 덮어쓰지 않는다.
6. 규정 이력은 보존하고 현행 버전 전환은 한 트랜잭션에서 처리한다. 동일 입력 재실행 시 중복·불필요한 새 버전이 생기지 않게 한다.
7. 기존 설명·요금·운영 메모 등 필드의 저장 위치를 정하고 보존한다. SQL 설계에 없는 필드는 명시적 스키마 확장으로 처리한다.
8. 전체 적재 오류는 롤백한다. 외래키·고유성·좌표·출처·정책 제한을 검증한다.

추천 어댑터는 `enabled=1`만 보지 않는다. 현행 검증 규정·근거·대전 주소/좌표·숫자 제한·카테고리별 필수 정보·미해결 필수 조건을 검사한다. 시간표의 요일·계절·휴무를 임의로 하나의 시간대로 합치지 않는다. 날짜나 체고 등 추가 입력이 반드시 필요한 상품은 현재 입력 흐름에서는 보류한다.

이번 서비스 전환에서 먼저 구현할 ETL은 서비스 장소·상품·정책·출처 영역이다. 방문자 통계·지역 순위 등 분석 데이터 이전은 별도 후속 작업으로 기록하며, 이 단계에서 전체 분석 데이터까지 이전했다고 표시하지 않는다.

### B-6. 구현할 CLI 계약 — 지금은 실행 불가

아래 모듈·옵션은 이번 작업에서 구현할 인터페이스다. 현재 있는 명령으로 오해하지 않도록 한다.

```powershell
# 구현 후: 변경 없이 변환·충돌·활성/보류 건수 검사
.\.venv\Scripts\python.exe -m scripts.migrate_service_db --source-db data/app.db --review-dir outputs/policy_review_20260925 --approved data/curated/approved_places.json --target-db data/app_normalized.db --dry-run

# 구현 후: 검증된 계획 적재
.\.venv\Scripts\python.exe -m scripts.migrate_service_db --source-db data/app.db --review-dir outputs/policy_review_20260925 --approved data/curated/approved_places.json --target-db data/app_normalized.db

# 구현 후: 추천 가능/보류 사유 확인
.\.venv\Scripts\python.exe -m scripts.check_live_readiness --database data/app_normalized.db
```

B는 데이터 중복 방지, 부분 실패 롤백, 현행 정책 유일성, NULL 보존, 필수 조건 미확인 후보 제외, 기존/정규화 `Place` 값 비교, 실제 모드에서 데모 제외를 테스트한다. 키 없는 자동 테스트는 모의 경로 응답으로 수행하고 실제 API 검사는 별도로 한다.

## 6. B: 카카오 키 설정·검사

### B-7. 키 준비 및 .env 생성 — 현재 실행 가능

카카오디벨로퍼스에서 앱을 등록/선택하고 **앱 → 플랫폼 키 → REST API 키**를 확인한다. 서비스 정보를 등록하고 호출 허용 IP를 설정했다면 실행 서버의 외부 통신 IP와 맞춘다. [공식 시작 가이드](https://developers.kakaomobility.com/guide/navi-api/start)

로컬 검색과 자동차 길찾기는 `Authorization: KakaoAK REST_API_KEY`를 사용한다. 두 API에서 같은 키가 동작하면 아래 두 변수에 같은 값을 넣을 수 있다. [로컬 API](https://developers.kakao.com/docs/ko/local/dev-guide), [자동차 길찾기 API](https://developers.kakaomobility.com/guide/navi-api/directions)

```powershell
if (-not (Test-Path .env)) {
    Copy-Item config/.env.example .env
}
notepad .env
```

현재 코드 기준 설정:

```dotenv
APP_MODE=live
DATABASE_PATH=data/app.db
KAKAO_REST_API_KEY=실제_REST_API_키
KAKAO_MOBILITY_API_KEY=실제_길찾기용_REST_API_키
LOCATION_SIGNING_KEY=
MAX_ROUTE_REQUESTS=500
MAX_SEARCH_STATES=250000
```

키는 로컬 편집기에서 입력한다. `LOCATION_SIGNING_KEY`는 비우면 앱이 별도 로컬 키 파일을 생성한다. 이미 PowerShell 환경변수에 같은 설정을 지정한 경우 그 값이 `.env`보다 우선하므로 B가 사용하는 터미널 설정도 확인한다.

### B-8. 실제 API 호출 검사 — 현재 실행 가능

장소 검색 1회와 자동차 길찾기 1회를 호출한다. 키는 출력하지 않는다.

```powershell
@'
from datetime import datetime, timezone
from app.core.config import Settings
from app.integrations.location_client import LocationClient
from app.integrations.route_client import RouteClient
from app.schemas.trip import Point

s = Settings.from_env()
if not s.kakao_key or not s.mobility_key:
    raise SystemExit('위치·경로 키를 모두 설정하세요.')
items = LocationClient(s.kakao_key).search('대전역')
print('장소 검색 결과:', len(items))
if not items:
    raise SystemExit('장소 검색 결과를 확인하세요.')
client = RouteClient(s.mobility_key)
try:
    leg = client.route(
        Point(name='대전역', latitude=36.332, longitude=127.434),
        Point(name='대전시청', latitude=36.3504, longitude=127.3845),
        datetime.now(timezone.utc).isoformat(),
    )
    print('경로 기준:', leg.route_basis)
    print('이동시간(초):', leg.duration_seconds)
    print('이동거리(m):', leg.distance_meters)
finally:
    client.close()
'@ | .\.venv\Scripts\python.exe -X utf8 -
```

성공 기준: 검색 결과가 있고, 경로 기준이 `kakao_current_TIME`이며 두 지점 간 거리·시간이 양수다. 실패하면 키 종류·API 이용 권한·호출 허용 IP·쿼터를 확인한다. 현재 클라이언트는 오류를 일반 메시지로 바꾸므로, 필요하면 B가 키를 제외한 HTTP 상태·제공사 오류 코드만 기록하는 진단을 추가한다.

## 7. B: 전환·복구 / A+B: 완료 확인

### B-9. 정규화 DB로 전환 — 구현·적재 검사 통과 후

서버를 종료하고 `.env`에서 다음 설정을 반영한다. `DATABASE_BACKEND`는 B가 구현해야 동작하는 신규 설정이다.

```dotenv
APP_MODE=live
DATABASE_BACKEND=normalized
DATABASE_PATH=data/app_normalized.db
```

기존 `app.db`는 복구용으로 보존한다. 최종 파일명이 반드시 `app.db`일 필요는 없다. 실제 조회 DB는 `DATABASE_PATH`가 결정한다. 정규화 전환 후에는 기존 `build_service_db`로 정규화 DB를 갱신하지 않고 새 적재기를 사용한다.

실행 터미널의 우선 설정도 일치시킨다.

```powershell
# 정규화 연결 구현·적재가 끝난 뒤 실행
$env:APP_MODE = 'live'
$env:DATABASE_BACKEND = 'normalized'
$env:DATABASE_PATH = 'data/app_normalized.db'
.\.venv\Scripts\python.exe -m scripts.run_service
```

앱: http://127.0.0.1:8000 / API 문서: http://127.0.0.1:8000/docs

다른 터미널에서 확인한다.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/healthz
```

현재 health의 `routing_connected=true`는 키 존재 여부만으로도 표시되고, 데모에서도 true다. 실제 호출 성공을 대신하지 않는다. B-8 결과와 함께 확인하고 새 점검기에서는 설정 여부와 실제 검사 결과를 구분한다.

### 공동 완료 기준

| 검사 | 담당 | 통과 기준 |
|---|---|---|
| 데이터 출처 | A | 추천된 모든 상품의 실제 업체·규정·확인일·근거 확인 |
| 활성 후보 | A+B | 목표 반려견 조건에서 숙소/식당/체험 최소 수량 충족, 보류 사유 해소 |
| DB 연결 | B | live에서 정규화 저장소 사용, 재실행 중복 없음, 외래키·무결성 검사 통과 |
| 장소 검색 | B | 실제 검색 API 응답 성공 |
| 경로 | B | 실제 API 응답의 도로 경로·이동시간 사용 |
| 당일·2일 추천 | A+B | 유효한 검색 위치로 요청, `recommended`, 결과 `is_demo=false`, 상품·조건 표시 일치 |
| 제한 초과 | A+B | 마릿수/체중이 제한을 넘으면 해당 장소 제외, 부족 시 이유 표시 |
| 화면·저장 | A+B | 데모 배너 없음, 상세 출처 표시, 저장·재조회·내보내기 확인 |

기존 브라우저에 저장된 데모 여행은 localStorage에 남을 수 있다. 새 실제 추천 결과와 구분해 확인한다. 배너가 사라졌다는 사실만으로 완료 처리하지 않는다.

전환 문제가 있으면 서버를 종료하고 `.env`와 실행 터미널을 기존 저장소로 돌린다. A의 승인 자료가 반영된 기존 `app.db`를 그대로 보존해야 이 복구가 가능하다.

```powershell
# .env도 APP_MODE=live, DATABASE_BACKEND=legacy, DATABASE_PATH=data/app.db로 변경
$env:APP_MODE = 'live'
$env:DATABASE_BACKEND = 'legacy'
$env:DATABASE_PATH = 'data/app.db'
.\.venv\Scripts\python.exe -m scripts.run_service
```

## 8. 각자 시작할 첫 작업

**A:** 기존 검토본을 읽고, 공통 양식에 맞춰 2일 여행용 실제 숙소·식당·체험 후보의 부족한 규정을 확인한다. 조사 결과와 미확인 항목을 B에게 전달한다.

**B:** DB를 백업하고, A에게 스키마·ID 규칙을 전달한다. 정규화 적재기와 조회 어댑터를 구현하는 동안 카카오 키를 설정하고 실제 API를 검사한다. A 자료 인계 후 시험 적재 → 실제 반영 → 공동 검증을 진행한다.
