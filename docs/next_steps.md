# 반려동물 시설 공급 부족순위 후속 작업

이 문서는 현재 관광수요 분석에 한국관광공사 반려동물 동반여행 API의 숙소·음식점 자료를 결합해 최종 순위를 만드는 작업 목록입니다.

## 2026-09-19 진행 상태

- 반려동물 동반여행 서비스 활용신청 및 `.secrets/pet_tourapi.key` 저장을 완료했고, `check`로 실제 접근권한을 확인했습니다.
- `region_monthly.csv`의 부산·인천·대전·강릉·전주 5개 지역, 2025-09~2026-07의 55개 지역·월 자료를 읽어 기간 완전성, 중복, 방문자 숫자 형식을 검증했습니다.
- `configure_tourapi_key.py --gui --service pet`으로 반려동물 전용 키를 마스킹 입력할 수 있도록 준비했습니다. 저장 대상은 `.secrets/pet_tourapi.key`입니다.
- 전체 시설 수집 완료: [runs/pet_api_20260919_183904](../runs/pet_api_20260919_183904)의 `places.csv`, `manifest.json`, `raw/`에 63건을 저장했습니다. 5개 광역 범위 × 2개 유형의 10개 조회를 완료했고, 전체 건수·수집 건수 일치와 원문/CSV 해시를 검증했습니다.
- API 반환 건수(숙박/음식점): 인천 1/1, 대전 1/0, 부산 5/1, 강원 18/27, 전북 9/0. 강원·전북은 도 전체이며, 강릉·전주는 다음 분석 단계에서 추립니다.
- 대전 음식점의 정상 0건 응답(`totalCount=0`, `numOfRows=0`)을 오류로 처리하던 파서를 수정했고, JSON/XML 및 비정상 응답 회귀 테스트 5개를 통과했습니다. 0건은 해당 API 조회에서 등록시설이 확인되지 않았다는 뜻입니다.
- 수요·공급 결합 및 계산 검증 완료: [순위 CSV](../runs/pet_supply_20260919_184024/pet_supply_ranking.csv), [검증 기록](../runs/pet_supply_20260919_184024/analysis_validation.json).
- 대상 시설 39건(숙박 17, 음식점 22)을 분석했고, 대상 지역 밖 시설 24건은 제외했습니다. content_id 중복과 주소 누락은 각각 0건입니다. 각 지역의 11개월 방문자 평균, 유형별 시설 수, 50:50 부족지수와 순위를 별도 재계산해 대조했습니다.
- 부족 추정순위: 대전 81.25 → 인천 75.00 → 전주 56.25 → 부산 37.50 → 강릉 0.00. 이는 5개 후보 내 상대점수이며, 부족률(%)이 아닙니다. 대전·전주 음식점의 API 등록 0건 처리에 영향을 받습니다.
- 남은 작업: 실제 영업 여부·반려견 허용조건 표본 확인, API 등록 범위의 편차 검토, 최종 개발 지역과 선정 근거 기록. 현재 결과만으로 최종 지역을 확정하지 않았습니다.

## 현재 구현된 내용

- `fetch_pet_tourapi.py`
  - 반려동물 동반여행 목록 API의 페이지별 원문 응답을 `raw/`에 보존
  - 집계용 `places.csv` 생성
  - 지역·콘텐츠 유형별 전체 페이지 수집 및 manifest 기록
- `analyze_pet_supply.py`
  - 숙박·음식점 유형 필터링
  - `content_id` 기준 중복 제거
  - 주소와 광역 areaCode를 사용한 대전·인천·부산·강릉·전주 분류
  - 2025-09~2026-07 11개월 평균 방문자와 결합
  - 시설당 방문자 부담도와 `shortage_index` 계산
  - `pet_supply_ranking.csv`, `pet_facilities_deduplicated.csv`, `unmatched_places.csv`, `pet_supply_audit.json` 생성
- `select_development_region.py`
  - 관광수요 후보 순위만 계산
  - 반려동물 시설 공급 순위는 `analyze_pet_supply.py`에서 별도 계산

## 사용자 준비 작업

### 1. 반려동물 API 활용신청

- 공공데이터포털 또는 한국관광공사 TourAPI에서 `한국관광공사_반려동물_동반여행_서비스`를 검색합니다.
- 방문자수 API에 사용한 키와 반려동물 서비스 키의 활용신청·접근권한이 같은지 가정하지 않습니다.
- 서비스 상세 화면에서 다음 항목을 확인합니다.
  - 실제 서비스 기본 URL
  - 목록 API operation 이름
  - 숙박·음식점 `contentTypeId` 코드
  - 일일 호출한도와 개발·운영 계정 구분

현재 수집기의 기본값은 다음과 같습니다. 서비스 명세가 다르면 실행 옵션을 수정해야 합니다.

```text
기본 URL: https://apis.data.go.kr/B551011/KorPetTourService2
목록 API: areaBasedList2
숙박 코드: 32
음식점 코드: 39
```

### 2. 키 파일 저장

인증키 한 줄만 별도 파일에 저장합니다. 기존 방문자 API 키 파일을 덮어쓰지 않습니다.

```text
.secrets/pet_tourapi.key
```

키 파일은 Git에 커밋하지 않습니다. 명령행에 키 문자열 자체를 직접 입력하지 않습니다.

마스킹 입력창으로 저장하려면 프로젝트 폴더에서 실행합니다.

```powershell
$pythonExe = 'C:\Users\ms840\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $pythonExe -X utf8 .\configure_tourapi_key.py --gui --service pet
```

### 3. API 연결 확인

프로젝트 폴더에서 실행합니다.

```powershell
$pythonExe = 'C:\Users\ms840\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$petKeyFile = '.secrets\pet_tourapi.key'
& $pythonExe -X utf8 .\fetch_pet_tourapi.py check --key-file $petKeyFile --area-code 3 --content-type-id 32
```

확인 실패 시 다음 순서로 점검합니다.

1. 키 파일에 공백·줄바꿈·따옴표가 포함되지 않았는지 확인합니다.
2. 공공데이터포털에서 반려동물 서비스 활용신청이 승인 또는 자동승인 상태인지 확인합니다.
3. 서비스 상세 명세와 `--base-url`, `--operation` 기본값이 일치하는지 확인합니다.
4. 개발계정 일일 호출한도를 초과하지 않았는지 확인합니다.

활용신청 전 기존 `.secrets/tourapi.key`로 시도한 반려동물 API 확인은 실패한 이력이 있습니다. 이 과거 결과로 현재 승인 상태를 판단하지 않으며, 새로 저장한 키로 연결을 확인합니다.

## 실행 작업

### 4. 시설 목록 수집

기본 수집 범위는 인천·대전·부산과 강원·전북입니다. 강원·전북은 도 단위 목록을 받은 뒤 주소로 강릉시·전주시만 남깁니다.

```powershell
& $pythonExe -X utf8 .\fetch_pet_tourapi.py fetch `
  --key-file $petKeyFile `
  --output .\runs\pet_api_20260915_01
```

수집 후 확인할 파일:

- `runs/pet_api_20260915_01/manifest.json`
- `runs/pet_api_20260915_01/places.csv`
- `runs/pet_api_20260915_01/raw/`

`manifest.json`에서 각 query의 전체 건수와 실제 수집 건수, 페이지 해시, 호출 횟수를 확인합니다.

### 5. 수요·공급 결합

```powershell
& $pythonExe -X utf8 .\analyze_pet_supply.py `
  --input .\runs\pet_api_20260915_01 `
  --demand .\region_monthly.csv `
  --start 2025-09 `
  --end 2026-07 `
  --output .\runs\pet_supply_202509_202607_01
```

### 6. 결과 검토

다음 순서로 검토합니다.

1. `pet_supply_ranking.csv`에서 `shortage_index`와 시설당 방문자 부담도를 확인합니다.
2. `pet_facilities_deduplicated.csv`에서 `content_id`가 중복되지 않는지 확인합니다.
3. `unmatched_places.csv`의 주소 누락·대상 지역 외 시설을 확인합니다.
4. `pet_supply_audit.json`에서 중복 제거 건수, 유형별 건수, 지역별 분류 건수, 경고를 확인합니다.
5. 시설 수가 0인 지역은 실제 시설이 전혀 없다는 뜻이 아니라 API 등록시설이 확인되지 않았다는 뜻으로 기록합니다.
6. API 수집일을 기록하고, 숙소·식당의 실제 영업 여부와 반려견 허용조건을 공식 홈페이지나 전화로 재확인합니다.

## 최종 해석 기준

`shortage_index`가 높을수록 2025-09~2026-07 일반 방문자 수에 비해 API 등록 반려동물 동반 숙소·음식점 수가 적은 지역입니다.

이 순위는 다음을 의미하지 않습니다.

- 반려견 동반 관광객의 실제 수요 순위
- 지역 내 모든 숙소·음식점의 전수 공급률
- 현재 영업 중인 시설 수의 보증
- 시설 규모·객실 수·좌석 수를 반영한 수용능력 순위

최종 보고서에서는 다음 표현을 사용합니다.

> 한국관광공사 API 등록시설 기준 관광수요 대비 반려동물 동반시설 공급 부족 추정순위

## 완료 조건

- [x] 반려동물 서비스 활용신청 완료 (2026-09-19 사용자 확인)
- [x] 반려동물 서비스 실제 접근권한 확인
- [x] `.secrets/pet_tourapi.key` 저장
- [x] `check` 성공
- [x] 시설 목록 전체 페이지 수집
- [x] `manifest.json`의 페이지·건수 점검
- [x] `content_id` 중복 제거 결과 점검
- [x] 주소 분류 누락 점검
- [x] 11개월 방문자 데이터와 결합
- [x] 숙소·음식점별 부담도와 종합 부족지수 검토
- [ ] 영업 여부와 반려견 이용조건 표본 확인
- [ ] 최종 개발 지역과 선정 근거 기록
