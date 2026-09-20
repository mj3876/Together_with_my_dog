# 우리 개와 끝까지 함께 — 대전 반려견 여행 서비스

> 지역 선정·분석 코드 6개와 이 문서는 `Together_with_my_dog_cityselection/`에 있습니다. 아래 명령은 모두 상위 저장소 루트 `Together_with_my_dog/`에서 실행합니다. 서비스 소스와 `.secrets/`, `data/`, `runs/`는 저장소 루트 기준입니다.

Python/FastAPI로 구현한 로컬 실행 서비스입니다. **대전 출발 위치, 여행 전체 일수, 반려견 수, 각 반려견 체중, 대전 종료 위치**만 입력하면 전체 이동시간이 짧은 **여행 코스 하나**를 제공합니다. 설계 원본은 [Notion 구현 가이드](https://app.notion.com/p/3e04a247b914812b8349e7052dd002b4)에서 관리합니다.

## 서비스 실행

Python 3.10 이상을 사용합니다. 아래는 PowerShell 기준이며 활성화 없이 가상환경의 Python을 직접 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m scripts.run_service --demo
```

브라우저에서 **http://127.0.0.1:8000**을 엽니다. API 문서는 **http://127.0.0.1:8000/docs**입니다. 종료는 실행 터미널에서 `Ctrl+C`입니다. 이미 `.venv`를 준비했다면 마지막 명령만 실행하면 됩니다.

Git Bash에서는 `.venv/Scripts/python.exe -m scripts.run_service --demo`를 사용합니다.

**데모 모드:** API 키 없이 동작합니다. 가상 숙소 2곳·식당 4곳·체험 4개와 가상 이동시간을 사용하며, 화면과 저장 결과에 데모임을 표시합니다. 별도 메모리 DB를 사용하므로 실제 DB에 섞이지 않습니다. 기본 위치 목록에서 출발·종료 지점을 선택하면 최대 4일 여행을 체험할 수 있습니다. 실제 방문용으로 사용할 수 없습니다.

**실제 모드:** 실제 장소·규정 자료와 경로 API 설정이 필요합니다. 데이터가 부족하면 그 이유를 표시하며 가상 장소나 직선거리 환산값으로 결과를 만들지 않습니다. 현재 기존 TourAPI 수집본만으로는 식당·체험을 채울 수 없으므로 아래 데이터 준비가 필요합니다.

```powershell
# .env가 없을 때 한 번만 복사하고, 편집기에서 실제 키를 입력합니다.
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m scripts.run_service
```

`.env`에서 `APP_MODE=live`로 설정합니다. PowerShell 환경변수 `APP_MODE`를 별도로 지정했다면 환경변수가 우선합니다.

| 설정 | 용도 |
|---|---|
| `KAKAO_REST_API_KEY` | 장소·주소 검색 및 현재 위치의 대전 행정구역 확인 |
| `KAKAO_MOBILITY_API_KEY` | 자동차 길찾기 `TIME` 기준 예상 주행시간 |
| `DATABASE_PATH` | 실제 SQLite 파일. 기본 `data/app.db` |
| `LOCATION_SIGNING_KEY` | 선택 위치·추천 응답의 변조 확인. 비어 있으면 `.secrets/location_signing.key`에 자동 생성 |
| `MAX_ROUTE_REQUESTS` | 한 추천 요청의 경로 조회 상한. 기본 500 |
| `MAX_SEARCH_STATES` | 정확 탐색의 상태 확장 상한. 기본 250000 |

키의 실제 서비스 사용 권한·요금·쿼터는 해당 제공사에서 설정합니다. REST 키는 서버에서만 사용합니다. [카카오 장소 검색 문서](https://developers.kakao.com/docs/latest/ko/local/dev-guide) · [카카오모빌리티 길찾기 문서](https://developers.kakaomobility.com/guide/navi-api/directions)

지도는 Leaflet/OpenStreetMap을 사용합니다. 인터넷 연결이 없으면 방문 위치 개요를 표시합니다. 점선은 방문 순서 연결선이고, 실제 경로가 확보된 구간은 도로 경로를 표시합니다. 배포할 때는 [지도 타일 사용 정책](https://operations.osmfoundation.org/policies/tiles/)에 맞는 타일 제공 방식을 선택하세요.

## 구현한 사용자 흐름

- 한 화면의 다섯 항목만 입력합니다. 여러 반려견의 체중은 각각 검사합니다.
- 1일은 숙박 없는 당일 코스, N일은 한 숙소에서 N−1박 하는 일차별 코스입니다.
- 하루 식당 1곳·체험 1개를 배치하고, 여행 중 같은 식당·프로그램을 반복하지 않습니다. 모든 끼니와 자유시간을 채우는 상품은 아닙니다.
- 마릿수·체중을 통과한 장소의 거점·일차별 배치·방문 순서를 함께 탐색합니다. 전체 주행시간 → 가장 긴 구간 → 안정적인 식별 키 순으로 결정합니다. 예산·취향 점수는 없습니다.
- 날짜를 입력받지 않으므로 운영·예약 확정 일정이 아닌 **날짜 미지정 참고 계획**입니다. 10:00 시작, 식사 60분, 구간당 준비 10분, 하루 8시간 이내를 자동 배치 기준으로 사용합니다. 실제 체험 소요시간이 없는 후보는 운영자가 보완해야 합니다.
- 최종 코스 하나의 일차별 지도·시간표·선정 이유·방문 전 확인사항을 보여줍니다. 장소 교체도 새 결과 하나만 반환합니다.
- 저장 버튼은 이 브라우저의 localStorage에만 저장합니다. JSON 내보내기·삭제·문의 문안 복사를 지원합니다. 문의 자동 발송·예약·결제는 없습니다.
- 날짜·견종·장비·인원 등 추가 조건을 묻지 않습니다. 입력하지 않은 조건의 충족 여부는 추정하지 않고 장소별 확인사항에 표시합니다.

후보가 부족하면 일수를 줄이지 않습니다. 경로를 조회하지 못하면 0분으로 채우지 않습니다. 탐색·호출 한도에 도달하면 일부 후보의 결과를 최적 코스처럼 반환하지 않고 `planning_limit` 또는 `route_unavailable` 상태를 반환합니다.

## 실제 데이터 준비

기존 분석·수집 파일은 `Together_with_my_dog_cityselection/`으로 이동했습니다. 서비스 명령은 프로젝트 루트에서 `python -m scripts.이름` 형식으로 실행합니다. 내려받은 자료·DB·실제 키는 Git에서 제외됩니다.

```powershell
# 1. 대전 숙박·음식점 목록 수집: 기존 수집기를 재사용합니다.
.\.venv\Scripts\python.exe -m scripts.collect_places --output data/raw/daejeon_01

# 2. 목록을 비활성 검토용 JSON으로 변환합니다. 기존 파일을 덮어쓰지 않습니다.
.\.venv\Scripts\python.exe -m scripts.import_manual_places --from-tourapi data/raw/daejeon_01/places.csv --output data/curated/tourapi_review.json

# 3. 필요한 장소의 동반 상세 원문을 수집합니다. contentId는 실제 수집값으로 교체합니다.
.\.venv\Scripts\python.exe -m scripts.collect_pet_details 3533154 --output data/raw/pet_details_01

# 4. 수동 입력 양식과 전체 데이터 스키마를 만듭니다.
.\.venv\Scripts\python.exe -m scripts.import_manual_places --template --output data/curated/manual_review.json
.\.venv\Scripts\python.exe -m scripts.import_manual_places --schema --output data/curated/place_schema.json

# 5. 공식 근거로 검토·보완한 JSON만 적재합니다. 같은 id는 갱신하며 전체 입력 오류 시 적재하지 않습니다.
.\.venv\Scripts\python.exe -m scripts.build_service_db data/curated/tourapi_review.json data/curated/manual_review.json
```

`collect_pet_details`의 기본 operation은 `detailPetTour2`이며 승인받은 최신 명세가 다르면 `--operation`으로 지정합니다. 목록·상세 수집에는 기존 `.secrets/pet_tourapi.key`를 사용합니다. API 응답의 자유서술 문장을 임의로 허용 규정으로 자동 변환하지 않습니다.

대전시 음식점 XLSX/CSV는 실제 명부의 헤더에 맞춰 변환합니다. 아래 `업소명`·`소재지`는 예시이므로 첨부 파일에 맞게 지정해야 합니다. 헤더가 첫 행이 아니면 `--header-row`, 다른 시트면 `--sheet`를 사용합니다.

```powershell
.\.venv\Scripts\python.exe -m scripts.import_restaurant_list data/raw/restaurants.xlsx --name-column 업소명 --address-column 소재지 --source-url "공식_게시물_URL" --output data/curated/restaurants_review.json
```

검토용 자료의 `latitude`·`longitude`와 업체명·주소를 실제 값으로 채우고, 다음 조건을 확인한 뒤 `active=true`로 변경합니다.

| 데이터 | 활성화에 필요한 내용 |
|---|---|
| 공통 | 대전 실제 주소·좌표, 공식 근거에 따른 `policy.pet_allowed`, `policy.verified`, `source_url`, `source_quote`, `checked_at` |
| 반려견 규정 | `max_dogs`, `max_weight_kg`, 체중 `weight_operator`(`lt`/`lte`). 무제한은 공식 근거가 있을 때만 `dogs_unlimited`/`weight_unlimited=true` |
| 숙소 | 동반 가능한 객실별 별도 `id`와 `product_name`. 같은 숙소의 객실은 `venue_id` 공유 |
| 식당 | 실제 식사 메뉴 확인 후 `serves_meals=true`. 동일 업체 지점의 중복 자료는 `venue_id`로 묶기 |
| 체험 | 실제 프로그램별 `id`·`product_name`, 상시/정기 운영 `recurring=true`, 공식 `duration_minutes` |
| 추가 규정 | 견종·체고·준비물·참가 자격은 `policy.requirements`에 기록. 운영·휴무·회차는 `schedule_note` |

비활성 후보는 DB에 보관할 수 있지만 추천하지 않습니다. 정식 자료가 없는 마릿수·체중 규정은 통과시키지 않습니다. 좌표 범위 검사만으로 행정구역을 확정하지 않으므로 수동 자료는 공식 주소도 확인해야 합니다. 파일 사이에서 같은 `id`가 반복되면 적재를 거부합니다. 데이터 관리 API를 인터넷에 노출하지 않고 CLI로 자료를 관리합니다.

## 서비스 코드 구성과 API

| 경로 | 역할 |
|---|---|
| `app/main.py`, `app/api/` | FastAPI 실행·화면·추천·장소·위치·교체·문의 API |
| `app/schemas/` | 다섯 입력, 장소별 규정, 일차별 일정과 단일 결과 형식 |
| `app/models/`, `app/db/`, `app/repositories/` | SQLite/SQLAlchemy 저장·조회. 초기에는 검증된 장소·정책·프로그램 문서를 하나의 테이블에 보관 |
| `app/services/` | 규정 처리, 정확 조합 탐색, 참고 시간표, 경로 재사용, 최종 선정 |
| `app/integrations/` | 카카오 위치·경로 API 및 기존 TourAPI 수집기 연결 |
| `app/templates/`, `app/static/` | 다섯 항목 입력, 단일 코스·지도·저장 화면 |
| `scripts/` | 실행, 원자료 수집·검토 양식·DB 적재·핵심 동작 점검 |

`POST /api/v1/recommendations`는 `start_point, trip_days, dog_count, dog_weights_kg, end_point`만 받습니다. 위치 객체는 `GET /api/v1/locations?q=검색어`의 결과를 그대로 사용합니다. 이름·주소·좌표와 서버 서명은 위치 선택 과정에서 채워지며 사용자 입력 조건을 늘리지 않습니다. 직접 좌표를 변조한 요청은 거부합니다.

그 밖에 `GET /api/v1/locations/resolve`, `GET /api/v1/places/{id}`, `POST /api/v1/itineraries/replace`, `POST /api/v1/itineraries/inquiry`, `GET /healthz`를 제공합니다. 교체·문의 요청은 서버가 서명한 코스 문맥을 사용합니다. 정확한 형식은 `/docs`에서 확인할 수 있습니다.

성공은 `status=recommended`, `itinerary={...}`입니다. `itinerary.days`는 같은 여행의 일차 목록입니다. 실패 시 `itinerary=null`과 이유를 반환하며, 사용자에게 여섯 번째 조건을 요구하지 않습니다.

```powershell
# 외부 API 호출 없이 핵심 서비스 동작 점검
.\.venv\Scripts\python.exe -m scripts.check_service
```

로컬 개발용 실행 범위입니다. 실행 명령은 127.0.0.1에만 바인딩합니다. 공개 배포·인증·사용자 계정·실시간 재고 연동은 포함하지 않습니다.

---

# 기존 지역 선정 · 데이터랩 분석 도구

한국관광공사 방문자 지표와 반려동물 동반시설 자료를 결합해 개발 후보 지역을 비교하는 Python 프로젝트입니다. 기존 README와 「개발 대상 지역 선정 | 데이터랩 기술 구현 가이드」를 이 문서로 통합했습니다.

**실행자는 인증키와 입력 데이터를 별도로 준비해야 하며, 숙박비율 CSV는 한국관광 데이터랩에서 직접 내려받아야 합니다.** 저장소에는 코드와 설명만 공유합니다. 인증키, API 원문, 다운로드 CSV, 가공 데이터와 실행 결과는 포함하지 않습니다.

입력 데이터는 API 자체가 아니라 **API에서 수집한 방문자·시설 응답과 직접 내려받은 숙박비율 CSV**입니다. API 응답은 수집 스크립트가 로컬에 저장하며, 숙박비율 파일은 실행자가 `data/raw/`에 넣습니다. 코드를 내려받는 것만으로 데이터까지 생기지는 않습니다.

## 1. 분석 목적과 범위

두 가지 결과를 계산합니다.

- **관광수요 후보 순위:** 월평균 외지인 방문자 지표와 월평균 외지인 숙박방문자 비율을 비교합니다.
- **API 등록시설 기준 관광수요 대비 반려동물 동반시설 공급 부족 추정순위:** 방문자 지표를 등록 숙박·음식점 수와 결합합니다.

현재 예시는 **대전·인천·부산·강릉·전주 전체**, **2025-09~2026-07의 공통 11개월**로 고정돼 있습니다. 기존 수집에서 2026-08은 1~15일만 반환되어 제외했습니다. 다시 조회한 자료의 완전성은 새 응답으로 검증해야 합니다.

| 후보 | 방문자 API 지역코드 | 원자료 단위 | 반려동물 API areaCode |
|---|---|---|---|
| 대전광역시 | `30` | `sido` | `3` |
| 인천광역시 | `28` | `sido` | `2` |
| 부산광역시 | `26` | `sido` | `6` |
| 강릉시 | `51150` | `sigungu` | `32`(강원 전체 조회 후 주소 분류) |
| 전주시 | `52110` | `sigungu` | `37`(전북 전체 조회 후 주소 분류) |

두 API는 지역코드 체계가 다릅니다. `--regions`와 `--area-codes`를 혼동하지 않습니다.

`--level city`는 광역시와 기초시를 시 전체 범위로 비교하는 설정입니다. 원자료의 `sido`·`sigungu` 등급을 유지하지만 행정 규모가 같다는 뜻은 아닙니다. 광역시와 그 산하 구처럼 범위가 겹치는 후보는 함께 비교하지 않습니다.

다른 후보·기간을 쓰려면 `prepare_city_comparison.py`의 `CANDIDATES`, `START`, `END`, `OUTPUT`, 입력 폴더 탐색 규칙과 수집·분석 옵션을 함께 바꿔야 합니다. 현재 순위 분석은 공통 11개월을 요구합니다. 코드가 임의의 지역·기간을 자동으로 선택하지 않습니다.

## 2. 환경과 코드 다운로드

아래의 기존 분석 스크립트는 Python **3.10 이상**과 표준 라이브러리만 사용합니다. FastAPI 서비스는 문서 상단의 `requirements.txt` 설치가 필요합니다. 키 입력 GUI는 `tkinter`가 있는 Python 설치에서 사용할 수 있으며, 없으면 터미널 입력을 사용합니다.

| 파일 | 역할 |
|---|---|
| `configure_tourapi_key.py` | 인증키를 마스킹 입력받아 로컬 파일에 저장 |
| `fetch_tourapi.py` | 방문자 API 호출·JSON/XML 응답 처리·일자 검증·월별 집계 |
| `fetch_pet_tourapi.py` | 반려동물 동반 숙박·음식점 전체 페이지 수집 |
| `prepare_city_comparison.py` | 방문자 원문과 숙박비율 CSV를 지역·월 기준으로 결합 |
| `select_development_region.py` | 관광수요 점수와 가중치별 순위 계산 |
| `analyze_pet_supply.py` | 시설 중복 제거·지역 분류·수요 결합·부족순위 계산 |

서로 공통 함수를 가져오므로 **6개 파일을 같은 폴더에 유지**합니다. `select_development_region.py`는 수집기에서도 월 계산에 사용합니다.

아래 명령은 Windows PowerShell 기준입니다. Git이 설치돼 있다면 원하는 작업 위치에서 실행합니다.

```powershell
git clone https://github.com/mj3876/Together_with_my_dog.git
cd Together_with_my_dog
python --version
```

Git이 없으면 GitHub의 **Code → Download ZIP**으로 받아 압축을 풀고 해당 폴더에서 터미널을 엽니다. `python` 대신 `py`가 동작하면 아래 명령의 `python`을 `py`로 바꿉니다. 둘 다 없으면 Python을 설치하고 PATH를 설정한 뒤 터미널을 다시 엽니다.

실행 파일의 전체 경로만 사용할 수 있다면 다음 형식을 사용합니다. 경로는 자신의 설치 위치로 바꿉니다.

```powershell
$pythonExe = 'C:\실제설치경로\python.exe'
& $pythonExe -X utf8 .\Together_with_my_dog_cityselection\fetch_pet_tourapi.py --help
```

## 3. 실행자가 직접 준비할 것

### 3-1. 두 API의 활용신청과 인증키

[공공데이터포털](https://www.data.go.kr/)에서 아래 서비스를 각각 확인하고 활용신청합니다. 한 서비스의 승인으로 다른 서비스도 사용할 수 있다고 가정하지 않습니다. 키 문자열이 같더라도 접근권한은 서비스별로 확인합니다.

| 용도 | 서비스 | 코드의 기본 주소 |
|---|---|---|
| 방문자 | [한국관광공사_빅데이터_지역별 방문자수_GW](https://www.data.go.kr/data/15101972/openapi.do) | `https://apis.data.go.kr/B551011/DataLabService` |
| 동반시설 | 한국관광공사_반려동물_동반여행_서비스 | `https://apis.data.go.kr/B551011/KorPetTourService2` |

방문자 수집기는 `metcoRegnVisitrDDList`(시도), `locgoRegnVisitrDDList`(시군구)를 사용합니다. 시설 수집기는 `areaBasedList2`, 숙박 유형 `32`, 음식점 유형 `39`를 사용합니다. 실행 전 명세·제공 기간·승인 상태·호출한도를 확인합니다. 반려동물 수집기의 주소·operation·유형은 CLI 옵션으로 바꿀 수 있습니다.

프로젝트 루트에서 차례로 실행하고, 각 창에 해당 키를 붙여넣어 저장한 뒤 창을 닫습니다.

```powershell
python -X utf8 .\Together_with_my_dog_cityselection\configure_tourapi_key.py --gui --service visitors
python -X utf8 .\Together_with_my_dog_cityselection\configure_tourapi_key.py --gui --service pet
```

GUI 없이 실제 대화형 터미널에서 입력하려면 `--gui`를 생략합니다. 입력은 화면에 표시되지 않습니다. 터미널 방식은 기존 키 덮어쓰기를 거부하므로 교체할 때는 GUI를 사용합니다.

```text
.secrets/tourapi.key       # 방문자 API 인증키
.secrets/pet_tourapi.key   # 반려동물 API 인증키
```

폴더·파일은 저장 시 생성됩니다. 따옴표 없이 인증키 한 줄만 저장합니다. 수집기는 포털의 Encoding/Decoding 키를 모두 처리합니다. 실제 키를 명령행·소스 코드·README에 넣거나 Git에 추가하지 않습니다.

### 3-2. 숙박방문자 비율 CSV 5개

숙박비율은 이 프로젝트의 방문자 API에서 제공되지 않습니다. [한국관광 데이터랩 지역별 관광 현황](https://datalab.visitkorea.or.kr/datalab/portal/loc/getAreaDataForm.do)에 접속해 필요한 경우 로그인하고 직접 내려받습니다.

1. **지역별 분석 → 지역별 현황 → 지역별 관광 현황**에서 후보 지역을 선택합니다.
2. **월간**, **2025-09~2026-07**로 맞춥니다. 추가 월이 있어도 지정한 11개월만 분석에 사용합니다.
3. **숙박/체류시간 → 숙박방문자 비율 추이(외지인)** 자료를 내려받습니다.
4. 대전광역시·인천광역시·부산광역시·강릉시·전주시를 각각 받아 총 5개 CSV를 준비합니다.
5. 프로젝트 루트에 폴더를 만들고 파일을 넣습니다.

```powershell
New-Item -ItemType Directory -Force .\data\raw | Out-Null
```

현재 결합 스크립트가 읽는 파일명과 헤더는 다음과 같습니다.

```text
data/raw/*숙박방문자 비율 추이(외지인).csv

필수 헤더: 기준연월,지역명,숙박방문자 비율
```

다운로드 시각이 앞에 붙은 원래 파일명을 사용할 수 있습니다. 파일명 끝은 `숙박방문자 비율 추이(외지인).csv`여야 합니다. 같은 지역 파일을 두 번 넣으면 중복 오류가 납니다.

| 항목 | 기대 형식 |
|---|---|
| 인코딩 | UTF-8 또는 UTF-8 BOM |
| 기준연월 | `202509`처럼 `YYYYMM` |
| 지역명 | 다섯 후보 중 한 지역의 정확한 이름 |
| 숙박방문자 비율 | `%` 없이 0~100 숫자. 23.5%는 `23.5` |
| 전국 평균 행 | 광역시는 `전국 광역지자체별 평균`, 강릉·전주는 `전국 기초지자체별 평균` |

현재 코드는 **각 파일에 후보 한 지역과 해당 전국 평균의 두 지역명이 들어 있는 형식**을 검증합니다. 전국 평균은 계산에서 제외합니다. Excel만 제공되거나 양식이 달라지면 원본을 별도 보존하고 분석용 CSV를 맞춰야 합니다. 없는 평균값을 만들어 넣거나 결측을 0으로 채우지 않습니다. 제공 형식 자체가 바뀐 경우에는 검증 코드도 수정해야 합니다.

다섯 지역의 기간·필터·단위·집계 정의가 같은지 확인합니다. 이 프로젝트는 데이터랩 자동 로그인이나 비공개 API 호출을 수행하지 않습니다.

## 4. 로컬 분석 실행 순서

모든 명령은 **프로젝트 루트**에서 실행합니다. 각 명령이 성공한 뒤 다음 단계로 넘어갑니다. 아래 방문자 수집 폴더명은 결합기가 찾는 이름과 연결되어 있습니다.

### 4-1. 방문자 API 연결 확인

```powershell
python -X utf8 .\Together_with_my_dog_cityselection\fetch_tourapi.py check --level sido --date 2025-09-01 --key-file .\.secrets\tourapi.key --output .\runs\visitor_check_01
```

`공식 API 정상 응답 확인`은 접근 확인 결과입니다. 전체 분석기간의 완전성은 다음 수집에서 검증합니다.

### 4-2. 시도·시군구 방문자 수집

```powershell
python -X utf8 .\Together_with_my_dog_cityselection\fetch_tourapi.py fetch --level sido --start 2025-09 --end 2026-07 --regions 30 28 26 --key-file .\.secrets\tourapi.key --output .\runs\api_candidates_sido_202509_202607

python -X utf8 .\Together_with_my_dog_cityselection\fetch_tourapi.py fetch --level sigungu --start 2025-09 --end 2026-07 --regions 51150 52110 --key-file .\.secrets\tourapi.key --output .\runs\api_candidates_sigungu_202509_202607
```

기본 방문자 유형은 `외지인(b)`입니다. `--regions`는 반환 자료에서 집계할 지역을 고르는 옵션입니다. API 전국 응답을 페이지별로 받으므로 조회량 자체가 다섯 지역으로 줄어들지는 않습니다. 월별 모든 일자와 지역·유형 일관성을 검증하며 호출한도 또는 불완전한 자료로 중단될 수 있습니다.

각 폴더에 `raw/`(페이지별 XML/JSON), `manifest.json`(요청·해시·상태), `visitors_monthly.csv`를 저장합니다. 정상 완료 상태는 `visitors_complete_overnight_required`로, 방문자 집계는 완료됐고 숙박비율은 별도 준비해야 한다는 뜻입니다.

### 4-3. 방문자·숙박비율 결합

API 수집 두 건과 숙박비율 CSV 5개가 준비된 뒤 실행합니다.

```powershell
python -X utf8 .\Together_with_my_dog_cityselection\prepare_city_comparison.py
```

옵션 없이 정해진 경로를 읽습니다. 방문자 폴더는 `api_candidates_*_202509_202607`을 먼저 찾고, 없으면 과거 실행용 `api_candidates_*_202509_202608`을 찾습니다. 새 사용자는 위 수집 명령의 `_202509_202607` 경로를 사용합니다.

정상 출력은 `overnight_months: 55`, `complete_visitor_months: 55`, `can_run_selection: true`입니다. `false` 또는 누락 월이 있으면 다음 분석 전에 입력부터 보완합니다.

- 루트 `region_monthly.csv`: 다음 두 분석기가 읽는 55행 입력.
- `data/processed/city_202509_202607/region_monthly.csv`: 결합 결과 보존본.
- 같은 폴더의 `visitor_coverage.csv`: 지역·월별 일자 완전성.
- 같은 폴더의 `source_audit.json`: 출처·해시·기간 검증 기록.
- 기존 루트 입력이 있으면 `previous_region_monthly.csv`로 백업한 뒤 교체합니다.

### 4-4. 관광수요 순위

```powershell
python -X utf8 .\Together_with_my_dog_cityselection\select_development_region.py --input .\region_monthly.csv --start 2025-09 --end 2026-07 --level city --output .\runs\city_selection_01
```

`region_ranking.csv`와 `selection_review.json`이 생성됩니다. `rank_base`, `rank_balanced`, `rank_visitors_only`를 비교합니다.

### 4-5. 반려동물 동반시설 확인·수집

```powershell
python -X utf8 .\Together_with_my_dog_cityselection\fetch_pet_tourapi.py check --key-file .\.secrets\pet_tourapi.key --area-code 3 --content-type-id 32

python -X utf8 .\Together_with_my_dog_cityselection\fetch_pet_tourapi.py fetch --key-file .\.secrets\pet_tourapi.key --output .\runs\pet_api_01
```

기본 조회는 인천·대전·부산·강원·전북 × 숙박·음식점입니다. 전체 페이지를 수집해 `raw/`, `places.csv`, `manifest.json`을 저장합니다. 성공 상태는 `complete`입니다. 정상 0건 응답도 처리합니다.

### 4-6. 수요 대비 시설 공급 부족순위

```powershell
python -X utf8 .\Together_with_my_dog_cityselection\analyze_pet_supply.py --input .\runs\pet_api_01 --demand .\region_monthly.csv --start 2025-09 --end 2026-07 --output .\runs\pet_supply_01
```

| 생성 파일 | 확인할 내용 |
|---|---|
| `pet_supply_ranking.csv` | 시설 수·시설당 방문자 지표·부족지수·순위 |
| `pet_facilities_deduplicated.csv` | 중복 제거 후 대상 지역으로 분류한 시설 |
| `unmatched_places.csv` | 식별자 누락 또는 대상 지역으로 분류되지 않은 시설 |
| `pet_supply_audit.json` | 중복 제거·유형 충돌·분류 건수·해시·경고 |

강원 중 강릉, 전북 중 전주만 포함하므로 대상 밖 시설이 `unmatched_places.csv`에 있는 것은 예상되는 결과입니다. 실제 주소 누락과 지역 밖 시설을 구분해 검토합니다. CSV/JSON은 로컬에 생성하며 Markdown 보고서는 자동 생성하지 않습니다.

## 5. 입력 검증과 계산 방법

### 지역×월 공통 입력

`region_monthly.csv`는 공식 API 형식이 아니라 프로젝트 입력 형식입니다.

```text
region_code,region_name,region_level,month,visitors,overnight_pct,visitor_source,overnight_source
```

한 행은 한 지역의 한 달입니다. 코드는 문자열, 월은 `YYYY-MM`, 방문자 지표는 유한한 0 이상, 숙박비율은 0~100 숫자로 저장합니다. 두 source 열에는 원본 경로를 기록합니다. `--level city`는 원자료의 `sido`·`sigungu`를 유지합니다. `--level sido` 또는 `sigungu`는 해당 단위만 허용합니다.

중복 지역코드+월, 이름 불일치, 필수 열·값 누락, 기간 밖 월, 11개월 미충족, 음수·NaN·무한대, 숙박비율 범위를 검사합니다. 후보가 두 곳 미만이면 순위를 계산하지 않습니다. 단위·원본 진위·행정경계·집계 정의는 별도 대조해야 합니다.

직접 정규화할 때는 방문자·숙박비율을 `region_code + month`로 1:1 결합합니다. 월만으로 결합하거나 누락 월을 삭제하지 않습니다. 가로 월은 행으로 바꾸고, 천 명/명 또는 0~1/0~100 단위를 확인합니다. 결측값은 0으로 채우지 않습니다.

### 관광수요 점수

`V`는 11개월 방문자 지표의 단순평균, `O`는 숙박비율의 단순평균입니다. 값이 작은 순서로 평균 동률 순위를 매겨 `P(x) = (평균 동률 순위 - 1) / (후보 수 - 1)`로 변환합니다. 모두 같은 값이면 P는 0.5입니다.

| 설정 | 점수 |
|---|---|
| 기본형 | `100 × (0.7 × P(V) + 0.3 × P(O))` |
| 균형형 | `100 × (0.5 × P(V) + 0.5 × P(O))` |
| 방문 중심형 | `100 × P(V)` |

가중치는 프로젝트의 비교 가정이며 검증된 최적값이 아닙니다. 후보를 바꾸면 점수도 바뀝니다. 점수 동점은 공동 등수(1, 1, 3)를 사용합니다. 코드는 동점 행 정렬에만 쓰고, 순위 비교 전 반올림하지 않습니다. 가중점수는 유리수로 계산합니다.

가상 A·B·C의 V가 1,000·500·100, O가 10·50·5라면 기본형은 85·65·0점입니다. 균형형에서는 A와 B가 각각 75로 동점입니다. 기본형 상위 3~5곳이 다른 가중치에서도 상위권인지 검토합니다.

### 시설 공급 부족 추정

숙박·음식점을 선택해 `content_id`로 중복 제거하고 주소·광역 areaCode로 분류합니다. 유형별 부담도는 `V ÷ 등록시설 수`이며 기본 부족지수는 `100 × (0.5 × P(숙박 부담도) + 0.5 × P(음식점 부담도))`입니다. `--lodging-weight`로 숙박 가중치를 바꿀 수 있습니다.

시설 0건이면 나눗셈 결과는 CSV에 공란으로 남기고 순위에서는 가장 높은 부담으로 처리합니다. 여러 지역이 0건이면 동률입니다. 0건은 실제 시설 부재를 입증하지 않으므로 API 등록 범위와 조건을 확인합니다.

### 해석과 최종 지역 선정

관광수요 점수는 데이터랩 공식 지수가 아닙니다. 부족지수는 실제 부족률(%)이나 객실·좌석 수용능력이 아닙니다. API 등록 범위·조회일·영업 여부·반려견 허용조건은 별도 확인합니다.

데이터랩은 방문자 지표의 일자 간 중복과 탭별 집계 기준 차이를 안내합니다. 방문자 합계를 고유 관광객 수로 해석하거나 V와 O를 곱해 숙박객 수를 추정하지 않습니다. O는 월별 비율의 단순평균으로 연간 방문자 가중비율과도 다릅니다. [공식 지표 유의사항](https://datalab.visitkorea.or.kr/datalab/portal/loc/getAreaDataForm.do)

일반 방문자 지표는 반려견 동반 수요의 대리변수이며 실제 동반 여행객 수가 아닙니다. 점수 1위를 자동 확정하지 않고 월별 추이·가중치별 순위·등록 편차·실제 시설 조건·DB 구축 범위를 검토합니다. 전국을 조사하지 않았다면 “분석한 다섯 지역 중 비교 결과”로 설명합니다.

검토 JSON의 `developer_review_required`는 이런 판단이 남아 있다는 뜻입니다. SHA-256은 사용 파일 식별값이며 자료의 정확성을 인증하지 않습니다. 최종 결정 시 후보·기간·점수·가중치 변화·선정 이유·출처·시설 조회일을 함께 기록합니다.

## 6. 재실행과 오류 대응

| 상황 | 대응 |
|---|---|
| Python 명령 없음 | 설치·PATH 확인 또는 `py`, 실행 파일 전체 경로 사용 |
| 인증·권한 오류 | 키 경로와 해당 서비스 활용 승인 상태 확인 |
| 네트워크 오류 | 인터넷·프록시·인증서·API 서비스 상태 확인 |
| 호출한도 초과 | 한도 초기화 또는 허용된 한도 조정 후 재수집 |
| 일자 누락 | 제공 기간·완전성 확인. 누락일을 0으로 만들지 않음 |
| 숙박자료 부족·중복 | 5개 지역·11개월·파일명·열 구성·중복 다운로드 확인 |
| 원본 폴더 없음 | 4-2의 정해진 이름으로 먼저 수집 |
| 출력 폴더 이미 존재 | 기존 결과를 보관하고 새 경로로 실행 |

수집기는 중단한 폴더에 이어받지 않습니다. 재수집할 때는 기존 폴더를 다른 이름으로 보관하고 **4-2에 지정된 이름**으로 다시 수집하거나 결합 코드의 경로도 바꿉니다. 결합기는 출력 `data/processed/city_202509_202607`이 고정이므로 재실행 전에 이전 결과 폴더를 다른 이름으로 보관합니다. 순위만 재계산할 때는 `--output`을 `_02` 같은 새 이름으로 바꾸면 됩니다.

실행 후 manifest 성공 상태·전체 건수·해시, `can_run_selection`, 시설 유형별 건수와 제외 사유를 확인합니다. 중단·입력 오류를 해결하지 않은 채 다음 단계로 넘어가지 않습니다.

## 7. GitHub 공개 범위

관리할 파일은 **`Together_with_my_dog_cityselection/` 안의 Python 스크립트 6개, README, `.gitignore`**, 저장소 루트의 **`.gitignore`, `app/`, `scripts/`, `requirements.txt`, `.env.example`**입니다. 루트 `.gitignore`는 공개할 폴더와 서비스 소스만 허용하고, 지역 선정 폴더의 `.gitignore`는 해당 폴더 안의 파일 8개만 허용합니다. 인증키·실제 `.env`·가상환경·데이터·DB·실행 결과는 계속 제외합니다.

로컬 `.secrets/`, `data/`, `runs/`, `region_monthly.csv`, 캐시·가상환경은 업로드하지 않습니다. 이미 추적 중인 파일은 `.gitignore`만으로 제외되지 않으므로 `git ls-files`와 `git diff --cached --name-only`에서 업로드 목록을 확인합니다. 다른 사용자는 위 3~4절에 따라 자신의 키와 자료를 준비합니다.
