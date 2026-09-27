# 실제 데이터 전환 작업 현황

2026-09-27 업데이트. 사용자 요청에 따라 미확인 제한을 추가 입력 없이 처리하는 참고 추천 기준을 적용했다. 위치 검색·길찾기 API가 모두 성공했고, 실제 카카오 경로로 2일 코스 생성에 성공했다.

## 현재 적용 기준

- 출발·종료 위치, 여행 일수, 반려견 수·체중의 기존 다섯 입력만 사용한다.
- 숙소 등의 마릿수·체중 제한이 미확인이면 추천 계산에서 제한을 적용하지 않는다. 명시된 숫자 제한은 계속 적용한다.
- 식당 좌표는 카카오 주소 검색으로 68곳 모두 정확한 주소와 일치하는 결과를 확보했다. 사용자에게 좌표·메뉴·동반 공간을 묻지 않는다. 메뉴·공간 미확인은 장소 상세에 표시한다.
- 체험 소요시간이 없으면 일정 계산용 60분을 사용한다. 기본 시간임을 표시하며, 실제 소요시간 원본 필드에는 NULL을 유지한다.
- 운영 방식·참가 조건은 추가 설문 대신 안내한다. 반려견 동반 허용 자체가 미확인인 프로그램 2건은 제외한다.
- 활성 참고 후보: 숙소 1개, 식당 68개, 체험 6개, 총 75개. 업체 규정 전체를 검증 완료했다는 뜻은 아니다.
- 운영 기본값은 `reference_planning` 테이블에 분리하고, 미확인 원본 규정을 확인된 무제한으로 바꾸지 않는다.
- 전체 후보를 유지한 채 경로 병렬 조회와 일차별 최소 이동시간 하한으로 탐색량을 줄였다.
- 실제 2일 코스 검사: 반려견 2마리(5kg·20kg), 약 11초, 모든 경로 `kakao_current_TIME`, `recommended` 반환 및 서명 검사 통과.
- 실행 서버에서 카카오 장소 검색과 식당 교체 성공. 교체하지 않은 숙소·다른 일차 식당 유지 확인. 기존 검사 12개와 정규화/참고 추천 검사 13개, 총 25개 통과.

기본값 적용 명령(최초/추가 자료 반영 후):

```powershell
.\.venv\Scripts\python.exe -m scripts.prepare_reference_catalog --geocode --activity-minutes 60
```

좌표가 이미 있는 장소는 재조회하지 않는다. 원본 파일이나 승인 상태는 변조하지 않는다.

검사 파일: `data/live_transition/live_reference_smoke.json`, `reference_preparation.json`, `reference_http_verification.json`.

## 반영한 내용

- 기존 `data/app.db`를 SQLite backup으로 보존한 후 검토 자료 9건 반영.
- `data/app_normalized.db`에 70개 실제 장소, 77개 상품·공간 후보, 음식점 등록 69건 이전.
- 현재 자료 구성: 음식점 후보 68개, 숙박 1상품, 공원 공간·교육 8개. 최초 엄격 검증 기준에서는 활성 0개였으며, 현재 참고 추천 기준에서는 75개다.
- 출처 파일 해시 검증, 원문/검토 레코드 연결, 규정 이력, NULL 보존, 반복 적재 중복 방지, 실패 롤백 구현.
- 추천·상세·교체·health가 정규화 저장소를 사용하도록 연결. 데모는 별도 메모리 DB 유지.
- health에서 API 키 설정 여부와 실제 연결 검사 여부를 구분.
- `.env`에 카카오 키 입력 완료. 카카오맵 활성화 후 위치 검색과 길찾기 모두 성공했고 서버를 재시작했다.
- 기존 회귀 검사 12개와 정규화 DB 검사 9개, 총 21개 통과. 실제 HTTP에서 live/normalized 상태·실제 장소 상세·데모 배너 제거·후보 부족 응답 확인.
- 검사 결과: `data/live_transition/readiness.json`, `data/live_transition/http_verification.json`.

지역 선정 통계·분석 결과 전체 ETL은 이번 서비스 장소 DB 이전 범위에 포함되지 않는다.

## 실행

루트 `.env`의 `APP_MODE=live`, `DATABASE_BACKEND=normalized`, `DATABASE_PATH=data/app_normalized.db`를 사용한다.

```powershell
.\.venv\Scripts\python.exe -m scripts.run_service --live
```

접속: http://127.0.0.1:8000 / 상태: http://127.0.0.1:8000/healthz

현재 실제 장소와 도로 경로로 참고 코스를 생성한다. 데이터가 부족하거나 경로·탐색 한도에 걸리면 사유를 표시하고 데모로 대체하지 않는다.

## 키 발급 후

현재 키 입력·카카오맵 활성화·서버 재시작 완료. 새 환경에서는 카카오디벨로퍼스의 해당 앱에서 **카카오맵 → 사용 설정 → 상태 ON**을 적용해야 한다. [공식 설정 안내](https://developers.kakao.com/docs/ko/kakaomap/common).

[카카오 공식 발급 안내](https://developers.kakaomobility.com/guide/navi-api/start)에 따라 앱의 플랫폼 키에서 REST API 키를 확인하고 `.env`의 `KAKAO_REST_API_KEY`, `KAKAO_MOBILITY_API_KEY`를 입력한다. 키가 각 API에서 허용되는지 실제 호출로 검사한다.

```powershell
.\.venv\Scripts\python.exe -m scripts.check_live_readiness --database data/app_normalized.db --check-api --output data/live_transition/readiness.json
```

키 값을 출력하지 않는다. `missing_key`는 미설정, `failed`는 키·권한·IP·쿼터·연결 검토가 필요하다는 뜻이다. 설정 변경 후 실행 중인 서버를 재시작한다.

## 업체 규정의 검증 수준을 높이는 후속 작업

숙박: 빨간대문 독채의 마릿수·체중 상한 및 필수 조건 확인.

음식점: 좌표, 식사 메뉴, 동반 공간, 마릿수·체중·견종 조건 확인. 등록 명부만으로 무제한 허용을 추정하지 않는다.

체험: 상시/정기 운영, 실제 소요시간, 동반 범위 확인. 공원의 체고·접종·등록 조건과 교육의 회차·자격 조건은 현재 입력으로 판정하지 않으며 장소별 확인사항으로 안내한다.

추가 공개 조사에서도 활성화에 충분한 일관된 공식 조건은 확보하지 못했다. [캠프향기 고캠핑 소개](https://gocamping.or.kr/bsite/camp/info/read.do?c_no=3059&viewType=read05)는 실제 후보 탐색에 활용할 수 있으나, 운영자 원문에서 상품별 숫자 제한을 추가 확인해야 한다. [베가시티 예약 페이지](https://www.yeogi.com/domestic-accommodations/74907)는 검색 요약의 동반 가능 안내와 열람된 본문의 동반 불가 문구가 달라 활성화 근거로 사용하지 않았다. 검색 요약만으로 승인하지 않는다.

검증 자료를 `data/curated/approved_places.json`으로 작성한 후:

```powershell
.\.venv\Scripts\python.exe -m scripts.migrate_service_db --approved data/curated/approved_places.json --dry-run
.\.venv\Scripts\python.exe -m scripts.migrate_service_db --approved data/curated/approved_places.json
.\.venv\Scripts\python.exe -m scripts.check_live_readiness --database data/app_normalized.db --output data/live_transition/readiness.json
```

엄격 검증 모드에서는 `policy.requirements`의 미판정 조건을 보류한다. 현재 활성화한 참고 추천 모드에서는 원문 조건을 유지하고 사용자에게 추가 입력을 요구하지 않으며, 장소 상세와 방문 전 확인사항에 표시한다. 실제로 그 조건을 충족한다고 확정하지 않는다.

## 검증과 복구

```powershell
.\.venv\Scripts\python.exe -m scripts.check_service
.\.venv\Scripts\python.exe -m scripts.check_normalized_db
```

두 번째 명령은 임시 DB에서만 테스트 데이터를 사용한다. 실제 데이터 DB에는 가상 활성 장소를 삽입하지 않는다.

백업 위치는 `data/live_transition/backup.json`에 기록한다. 전환 복구 시 서버를 종료하고 `.env`의 `DATABASE_BACKEND=legacy`, `DATABASE_PATH=data/app.db`로 변경한다. 같은 이름의 PowerShell 환경변수가 있으면 함께 변경한다.

정규화 DB에는 `scripts.build_service_db`를 사용하지 않는다. 기존 비활성 조사본을 활성 검증 자료보다 나중에 기존 DB에 적재하면 상태가 덮어써질 수 있으므로, 이후 자료 갱신은 새 정규화 적재기로 진행한다.
