"""저장된 실제 응답 재현 증거를 설명 열이 있는 검토용 결과로 작성한다."""
import ast
import csv
import hashlib
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'outputs/region_review_20260924'
OUT.mkdir(parents=True, exist_ok=True)
TMP = ROOT/'tmp/region_review_20260924'
SRC = ROOT/'Together_with_my_dog_cityselection'
E = json.loads((TMP/'evidence.json').read_text(encoding='utf-8'))

def read_csv(p):
    with p.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def write_csv(p, rows, fields=None):
    with p.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields or list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def function_ref(file, name):
    tree=ast.parse((SRC/file).read_text(encoding='utf-8'))
    node=next(n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
    return f'Together_with_my_dog_cityselection/{file}:{node.lineno} {name}()'

F=lambda file,name:function_ref(file+'.py',name)
fetch_ref=F('fetch_pet_tourapi','normalise_place')
summary_ref=F('fetch_tourapi','summarize_month')
city_ref=F('prepare_city_comparison','main')
supply_ref=F('analyze_pet_supply','main')
classify_ref=F('analyze_pet_supply','classify_place')
rank_ref=F('analyze_pet_supply','percentile')
pet_folder=ROOT/'runs/pet_api_20260919_183904'
supply_folder=ROOT/'runs/pet_supply_20260919_184024'
city_folder=ROOT/'data/processed/city_202509_202607'
monthly=read_csv(city_folder/'region_monthly.csv')
ranking=read_csv(supply_folder/'pet_supply_ranking.csv')
counts=defaultdict(int)
for r in E['daily']:
    if r['month']!='2026-08':counts[(r['region_code'],r['month'])]+=1

files=[]
def annotated(src, name, annotate):
    rows=read_csv(src)
    output=[{**r,**annotate(r)} for r in rows]
    write_csv(OUT/name,output)
    # All original columns and values must remain exactly equal, including blanks.
    saved=read_csv(OUT/name)
    assert [{k:r[k] for k in rows[0]} for r in saved]==rows
    files.append({'file':name,'source':str(src.relative_to(ROOT)).replace('\\','/'),'rows':len(rows),'original_columns_unchanged':True})

annotated(pet_folder/'places.csv','01_places_주석.csv',lambda r:{
    '주석_입력원문':'runs/pet_api_20260919_183904/'+r['source_file'],
    '주석_변환':f"contentid={r['content_id']} → content_id; contenttypeid={r['content_type_id']} → content_type_id; areacode={r['area_code']} → area_code. 이름·주소·좌표를 보존하고 query_*와 source_file을 추가.",
    '주석_근거함수':fetch_ref,
    '주석_해석':'API 등록 콘텐츠. 이 단계는 중복 제거·후보 도시 분류·반려견 규정 확인을 하지 않음.'})
annotated(supply_folder/'pet_facilities_deduplicated.csv','02_pet_facilities_deduplicated_주석.csv',lambda r:{
    '주석_정제':f"content_id로 중복 제거 후 type={r['content_type_id']}를 {r['category']}로 분류. addr1+addr2 주소가 {r['region_name']}에 해당하여 포함.",
    '주석_출처':'runs/pet_api_20260919_183904/'+r['source_file'],
    '주석_지역코드':f"관광 area_code={r['area_code']}를 직접 조인하지 않고 지역 분류 결과의 행정 region_code={r['region_code']}를 부여.",
    '주석_근거함수':F('analyze_pet_supply','normalise_place')+'; '+classify_ref+'; '+supply_ref,
    '주석_제외열':'places.csv의 mapx/mapy, query_area_code/query_content_type_id는 이 출력에 저장하지 않음. 시설 수 집계에 좌표는 사용하지 않음.'})
annotated(supply_folder/'unmatched_places.csv','03_unmatched_places_주석.csv',lambda r:{
    '주석_실제제외사유':f"주소가 {' '.join(r['addr1'].split()[:2])}로 비교 후보 5개 도시 밖에 있음. 현재 24행 모두 주소가 존재함.",
    '주석_reason해석':'unmatched_address는 주소 누락만 의미하지 않으며 대상 지역 밖도 포함.',
    '주석_근거함수':classify_ref})
annotated(supply_folder/'pet_supply_ranking.csv','04_pet_supply_ranking_주석.csv',lambda r:{
    '주석_평균방문자':'region_monthly.csv의 해당 region_code 11개월 visitors 산술평균. 숙박비율은 이 지수에 사용하지 않음.',
    '주석_부담도':f"월평균 방문자 지표 / 시설 수. 숙박 {r['pet_lodging_count']}건, 음식점 {r['pet_restaurant_count']}건. 0건이면 비율은 빈칸, 내부 순위 계산은 inf.",
    '주석_지수산식':f"100 × (0.5 × {r['lodging_shortage_percentile']} + 0.5 × {r['restaurant_shortage_percentile']}) = {r['shortage_index']}",
    '주석_순위':'1 + 자신보다 shortage_index가 큰 지역 수. 동점 공동순위; 같은 점수의 표시 순서는 region_code 오름차순.',
    '주석_근거함수':F('analyze_pet_supply','load_demand')+'; '+rank_ref+'; '+supply_ref,
    '주석_해석':'일반 관광수요 대비 API 등록시설 공급 부족 추정지수. 실제 공급 부족률이나 반려견 방문자 수가 아님.'})
annotated(city_folder/'region_monthly.csv','05_region_monthly_주석.csv',lambda r:{
    '주석_방문자집계':f"touDivNm=외지인(b), 행정코드={r['region_code']}, {r['month']}의 {counts[(r['region_code'],r['month'])]}일 touNum을 Decimal로 합산한 값={r['visitors']}.",
    '주석_숙박비율':f"다운로드 CSV의 해당 지역·월 '숙박방문자 비율'={r['overnight_pct']}%를 그대로 보존. 전국평균과 기간 밖 행 제외.",
    '주석_결합키':'region_code+month. 방문자 합계와 숙박비율을 나란히 결합하며 곱하지 않음.',
    '주석_근거함수':summary_ref+'; '+city_ref,
    '주석_완전성':'날짜 누락·중복·음수·비유한수는 집계 오류. 광역시와 기초시의 시 전체 범위 비교이며 동일 행정 규모가 아님.'})
annotated(city_folder/'visitor_coverage.csv','06_visitor_coverage_주석.csv',lambda r:{
    '주석_판정':f"해당 지역·월의 외지인(b) 자료 관측일 {r['observed_days']}일. summarize_month가 달력 날짜 집합과 정확히 일치하는지 검증하여 status={r['status']}.",
    '주석_근거함수':summary_ref+'; '+city_ref})

daily=[{**r,'주석_분석사용':'제외: 2026-08은 15일만 수집됨' if r['month']=='2026-08' else '포함: 월별 visitors에 합산', '주석_원문필터':'touDivNm=외지인(b); sido=areaCode, sigungu=signguCode', '주석_근거함수':summary_ref} for r in E['daily']]
daily.sort(key=lambda r:(r['region_code'],r['baseYmd']))
write_csv(OUT/'07_방문자_실제일별근거.csv',daily)

pet_comments={
 'raw_record_count':'input_files가 places.csv 하나를 선택하고 load_places가 읽은 63행.',
 'selected_category_record_count':'content_id가 있고 유형 32/39인 63행.',
 'unique_content_id_count':'content_id를 키로 quality 점수가 더 높은 행을 보존. 실제 중복 제거 0건, 63개 ID.',
 'classified_record_count':'classify_place가 후보 5곳으로 분류한 39행. 전부 address 방식.',
 'unmatched_record_count':'24행. 실제 주소는 모두 강릉/전주 이외 강원/전북 지역.',
 'region_counts':'후보 행의 region_code와 category별 콘텐츠 수.',
 'lodging_weight':'0.5. 음식점 가중치는 1-0.5.',
 'demand_sha256':'현재 root region_monthly.csv와 processed 결과의 해시가 일치하는지 재검증함.',
 'demand_file/facility_input/source_files':'과거 실행 폴더명이 남은 절대경로. 현재 프로젝트의 동일 상대경로로 찾고 해시/재현 결과를 확인함.',
 'status':'developer_review_required는 결과가 생성되어도 한계와 기준에 대한 검토가 필요하다는 기존 상태.',
 'warnings':'기존 문구의 n.a.는 개념 설명. 실제 CSV 저장 값은 빈칸. 주소 없음만 제외한다는 문구는 실제 코드보다 좁음.'}
city_comments={
 'period/analysis_month_count':'2025-09~2026-07 공통 11개월.',
 'candidate_count/comparison_scope':'대전·인천·부산 sido, 강릉·전주 sigungu의 시 전체 5곳.',
 'excluded_months':'2026-08은 방문자 원문 1~15일뿐. 모든 5개 후보에서 직접 확인.',
 'overnight_sources':'5개 CSV에서 각각 11행 사용, 기간 밖 후보 1행 제외, 전국평균 12행 제외. 합계 55행 사용/5행 기간 제외/60행 전국평균 제외.',
 'complete_visitor_months':'summarize_month의 월 전체 날짜 검증을 통과한 55개 지역·월.',
 'can_run_selection':'coverage에 incomplete가 없다는 뜻. 대전 선정 자체를 확정하는 값이 아님.',
 'visitor_api_sources':'두 manifest의 전체 status는 failed이지만 8월 불완전 때문. 이전 11개월 원문은 각 월 검증 후 사용.',
 'input_sha256':'이 스크립트가 작성한 region_monthly.csv의 SHA-256. 원자료 318개 페이지 해시도 별도 확인.'}
for source,name,comments in [(supply_folder/'pet_supply_audit.json','08_pet_supply_audit_주석.json',pet_comments),(city_folder/'source_audit.json','09_source_audit_주석.json',city_comments)]:
    original=json.loads(source.read_text(encoding='utf8'))
    result={**original,'_review_comments':{'source_file':str(source.relative_to(ROOT)).replace('\\','/'),'notes':comments}}
    (OUT/name).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

field_notes={
 'content_id':'API 콘텐츠 ID. 중복 제거 키. 업소명 기준 중복 제거가 아님.',
 'content_type_id':'목록 유형. 현재 숙박 32/음식점 39 사용.',
 'title':'시설 콘텐츠 이름.', 'addr1':'기본 주소.', 'addr2':'상세 주소.',
 'area_code':'반려동물 TourAPI 관광지역 코드. 방문자 행정코드와 다름.',
 'sigungu_code':'반려동물 API 지역 내 시군구 코드. 방문자 signguCode와 직접 조인하지 않음.',
 'mapx':'경도 문자열. 수집 단계에서 숫자 변환/좌표 검증을 하지 않음.',
 'mapy':'위도 문자열. 부족순위 계산에는 사용하지 않음.',
 'query_area_code':'수집 요청 areaCode. 수집기에서 추가.',
 'query_content_type_id':'수집 요청 contentTypeId. 원문 유형이 없을 때 대체값.',
 'source_file':'시설 조회에 속한 원문 페이지 상대경로. 다중 페이지라면 세미콜론 연결.',
 'category':'content_type_id로 정한 lodging 또는 restaurant.',
 'classification_method':'address 또는 area_code. 현재 분류된 39행은 모두 address.',
 'reason':'missing_content_id 또는 unmatched_address. 현재 24행은 모두 후보 지역 밖.',
 'region_code':'방문자 API 기준 행정지역 코드. 시설은 주소 분류 후 해당 후보 코드를 부여.',
 'region_name':'후보 도시 이름.', 'region_level':'sido(대전·인천·부산) 또는 sigungu(강릉·전주).',
 'month':'YYYY-MM 기준월.', 'visitors':'해당 월 모든 날의 외지인(b) touNum 합계. 월 순방문자라고 단정할 수 없음.',
 'overnight_pct':'외지인 숙박방문자 비율 CSV의 백분율 수치. 14.9는 14.9%.',
 'visitor_source':'해당 월의 API 원문 페이지 목록. 목록 내 후보 지역·유형·일자로 추가 필터링.',
 'overnight_source':'해당 지역 숙박방문자 비율 다운로드 CSV.',
 'observed_days':'선택 지역·월·외지인 유형의 서로 다른 기준일 수.',
 'first_day':'실제로 관측된 최초 기준일 YYYYMMDD.', 'last_day':'실제로 관측된 최종 기준일 YYYYMMDD.',
 'status':'월 집계 성공 complete, 실패 incomplete.', 'detail':'월별 집계 오류 설명. complete면 CSV 빈칸.',
 'shortage_rank':'1+자신보다 큰 부족지수의 수. 동점 공동순위.',
 'analysis_start':'분석 시작월 2025-09.', 'analysis_end':'분석 종료월 2026-07.',
 'analysis_month_count':'공통 분석 월수 11.',
 'mean_monthly_visitors':'지역별 11개월 visitors 산술평균. 출력 소수 6자리 반올림.',
 'pet_lodging_count':'후보 지역으로 분류된 고유 content_id 중 lodging 건수.',
 'pet_restaurant_count':'후보 지역으로 분류된 고유 content_id 중 restaurant 건수.',
 'visitors_per_pet_lodging':'월평균 방문자/등록 숙박 수. 0개면 CSV 빈칸, 내부 부담도 inf.',
 'visitors_per_pet_restaurant':'월평균 방문자/등록 음식점 수. 0개면 CSV 빈칸, 내부 부담도 inf.',
 'lodging_shortage_percentile':'숙박 부담도의 후보 5곳 내 중간순위 백분위(0~1).',
 'restaurant_shortage_percentile':'음식점 부담도의 후보 5곳 내 중간순위 백분위(0~1). 0건인 2곳은 0.875.',
 'shortage_index':'100*(0.5*숙박 백분위+0.5*음식점 백분위). 상대지수이며 부족률이 아님.',
 'lodging_status':'숙박 0개 no_registered_facility, 그 외 registered_records.',
 'restaurant_status':'음식점 0개 no_registered_facility, 그 외 registered_records.'}
dictionary=[]
for item in files:
    original=read_csv(ROOT/item['source'])
    for key in original[0]:
        assert key in field_notes,key
        dictionary.append({'결과파일':item['source'],'열명':key,'설명':field_notes[key]})
write_csv(OUT/'10_결과파일_열별주석.csv',dictionary)

checks=dict(E['checks'])
before=json.loads((TMP/'before_ast.json').read_text(encoding='utf8'))
checks['code_ast_unchanged']=all(ast.dump(ast.parse((SRC/name).read_text(encoding='utf8')))==tree for name,tree in before.items())
assert checks['code_ast_unchanged']
protected=json.loads((TMP/'protected_sha.json').read_text(encoding='utf8'))
checks['original_files_unchanged']=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest for p,digest in protected.items())
assert checks['original_files_unchanged']
city_audit=json.loads((city_folder/'source_audit.json').read_text(encoding='utf8'))
supply_audit=json.loads((supply_folder/'pet_supply_audit.json').read_text(encoding='utf8'))
checks['overnight_source_hashes_match']=all(hashlib.sha256((ROOT/s['file']).read_bytes()).hexdigest()==s['sha256'] for s in city_audit['overnight_sources'])
checks['demand_hash_matches_original_audits']=hashlib.sha256((ROOT/'region_monthly.csv').read_bytes()).hexdigest()==city_audit['input_sha256']==supply_audit['demand_sha256']
assert checks['overnight_source_hashes_match'] and checks['demand_hash_matches_original_audits']
checks['annotated_csv_values_preserved']=files
(OUT/'검증결과.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

report=[]
def add(s=''):report.append(s)
add('# 지역 선정 자료와 분석 기준 점검 — 2026-09-24')
add('WBS 1.4 · 담당 B · 원문 → 실제 함수 → 정제 결과 → 집계 기준을 확인한 검토 자료입니다. 새 API 호출 없이 저장된 실제 응답을 사용했습니다.')
add('\n## 1. 오늘 B의 작업과 이번 완료 범위')
add('원본 엑셀 `상세 WBS!A11:I13`을 직접 읽었습니다. 오늘 B 작업은 1.4 지역 선정 자료와 분석 기준 점검, 1.5 장소 조사 목록·외부 평가 일정 확보, 1.6 공모 양식·신청 항목·파일 규격 확인입니다. 이번 작업은 1.4의 근거 확인에 해당합니다. WBS의 상태는 수정하지 않았습니다.')
add('1.4 완료 기준은 “비교 지역·기간·행정단위·지표 확정, 보완자료 목록”입니다. 아래 현재 기준과 보완 항목을 검토하여 확정하면 됩니다.')
add('\n## 2. 실제 파이프라인과 파일명 정정')
add('`configure_tourapi`라는 정제 스크립트는 없습니다. 실제 `configure_tourapi_key.py`는 키 저장 도구입니다. `prepare_city_cimparison`의 실제 파일명은 `prepare_city_comparison.py`입니다.')
add('```text\nconfigure_tourapi_key.save_key → .secrets/*.key (인증 설정만 수행)\n방문자 XML → fetch_tourapi.parse_payload / summarize_month\n             + 별도 숙박비율 CSV → prepare_city_comparison.main → region_monthly.csv\n시설 JSON → fetch_pet_tourapi.normalise_place → places.csv\n             + region_monthly.csv → analyze_pet_supply → 시설 정제표·공급 부족순위\n```')
add('방문자 수집 실행은 2026-08 불완전으로 중단되어 `visitors_monthly.csv`가 생성되지 않았습니다. 실제 결합은 저장된 XML을 `prepare_city_comparison`이 직접 읽고 `summarize_month()`를 호출하여 수행했습니다. 별도 관광수요 순위는 `select_development_region.py`의 역할이며 이 결합표 자체는 순위를 계산하지 않습니다.')
add('\n## 3. API 응답 JSON/XML 폴더')
add('| 역할 | 실제 폴더(프로젝트 루트 기준) | 원문 | 수집 상태 |\n|---|---|---:|---|')
for x in E['folders']:
    add(f"| {'시설' if 'pet_api' in x['folder'] else '방문자 '+x['level']} | [{x['folder']}/raw](../../{x['folder']}/raw) | {x['files']}개 / {x['actual_rows']:,}행 | {x['status']} |")
add('방문자 두 폴더의 failed는 8월 16~31일 누락 때문입니다. 분석에 사용한 2025-09~2026-07은 5개 후보 모두 월 전체 일자가 있습니다. 시설은 `pet_api_20260919_183904`가 완료 수집본입니다. 앞선 `pet_api_20260919_01`은 manifest가 running이고 원문 3개만 있어 이번 분석 입력이 아닙니다.')
add('원문 파일 이름과 조회 조건은 각 폴더의 `manifest.json`에서 연결합니다. 방문자 수집기는 선택 후보만 다운로드하지 않으므로 전국 반환 행을 보존합니다. 시설은 강원·전북 전체 조회 후 강릉·전주만 분석에 포함합니다.')
add('\n### 시설 API 10개 실제 조회')
add('| 원문 | areaCode | contentTypeId | 반환 건수 |\n|---|---|---|---:|')
for q in E['folders'][2]['queries']:add(f"| {q['files'][0]} | {q['area_code']} | {q['content_type_id']} | {q['rows_collected']} |")
add('\n## 4. 원문 데이터 항목과 코드 주석')
add('`fetch_tourapi.py`와 `fetch_pet_tourapi.py`에 실제 응답 항목 설명과 저장 위치를 주석으로 추가했습니다. 원문 XML/JSON은 해시 검증을 위해 수정하지 않았습니다.')
add('| 원문 필드 | 의미 / 처리 |\n|---|---|')
for a,b in [('baseYmd','방문자 기준일 YYYYMMDD'),('areaCode / areaNm','시도 방문자 응답의 행정코드·지역명'),('signguCode / signguNm','시군구 방문자 응답의 행정코드·지역명'),('daywkDivCd / daywkDivNm','요일 코드·이름. 집계 미사용'),('touDivCd / touDivNm','방문자 구분. 외지인(b), 실제 코드 2만 분석'),('touNum','해당 일자·지역·방문자 구분의 수치. Decimal로 월합산'),('contentid / contenttypeid','시설 콘텐츠 ID / 유형(32 숙박, 39 음식점)'),('title / addr1 / addr2','시설 이름 / 기본 주소 / 상세 주소'),('areacode / sigungucode','시설 관광지역 코드. 방문자 행정코드와 다른 체계'),('mapx / mapy','경도 / 위도. 수집 결과에 보존, 공급 분석에서는 제외'),('cat1/2/3, lclsSystm1/2/3','콘텐츠 분류 코드. 현재 집계 미사용'),('lDongRegnCd / lDongSignguCd','법정동 계열 지역 코드. 현재 집계 미사용'),('firstimage / firstimage2 / cpyrhtDivCd','이미지 주소 / 저작권 구분. 현재 집계 미사용'),('tel / zipcode / mlevel','연락처 / 우편번호 / 지도 레벨. 현재 집계 미사용'),('createdtime / modifiedtime','콘텐츠 생성·수정 시각. 수집일과 다름'),('resultCode / resultMsg','API 응답 상태'),('totalCount / pageNo / numOfRows','전체 건수 / 응답 페이지 / 응답 페이지 크기')]:add(f'| {a} | {b} |')
add('결과 CSV의 모든 원래 열은 [10_결과파일_열별주석.csv](10_결과파일_열별주석.csv)에서 설명합니다. 실제 시설 목록에는 마릿수·체중·객실별 허용 조건이 없습니다.')
add('\n## 5. 실제 시설 원문에서 정제 결과까지')
add(f"원문: [{E['examples']['pet']['file']}](../../{E['examples']['pet']['file']})")
add('```json\n'+json.dumps(E['examples']['pet']['record'],ensure_ascii=False,indent=2)+'\n```')
add(f'1. `{fetch_ref}`: 위 25개 필드에서 공통 9개를 선택하고 열명을 통일합니다. `contentid=3533154 → content_id=3533154`, `contenttypeid=32 → content_type_id=32`, `areacode=3 → area_code=3`입니다. 요청조건 2개와 원문 경로를 추가해 12열 `places.csv`에 기록합니다. 전체 63행이 원문에서 재현됐습니다.')
add(f"2. `{F('analyze_pet_supply','input_files')}`는 폴더 안 `places.csv`를 우선 선택합니다. `{F('analyze_pet_supply','normalise_place')}`가 공통 필드를 읽고, `main()`이 ID 누락 및 유형을 검사합니다. 63행 모두 ID가 있고 숙박/음식점에 해당합니다.")
add(f"3. `main()`이 content_id로 중복 제거합니다. `{F('analyze_pet_supply','quality')}`가 유형·이름·주소1·지역코드·시군구코드의 채워진 개수를 비교하며 동점이면 첫 행을 유지합니다. 이번 수집은 고유 ID 63개로 제거 0건입니다.")
add(f'4. `{classify_ref}`가 주소로 대전광역시에 매칭하여 방문자 측 `region_code=30`, `category=lodging`, `classification_method=address`를 부여합니다. 대전 숙박 1건이 됩니다. 이 단계는 반려견 규정이나 영업 여부를 검증하지 않습니다.')
add('5. 39건은 다섯 후보 지역에 포함되고 24건은 `unmatched_places.csv`로 이동합니다. 이번 24건은 모두 주소가 있으며 후보 밖 지역입니다. 원래 reason 이름 `unmatched_address`를 “주소 누락”으로만 읽으면 안 됩니다.')
add('| 제외 지역 주소 앞부분 | 건수 |\n|---|---:|')
for k,v in E['unmatched_address_prefixes'].items():add(f'| {k} | {v} |')
add('주석 결과: [01 수집표](01_places_주석.csv), [02 정제 시설](02_pet_facilities_deduplicated_주석.csv), [03 제외 시설](03_unmatched_places_주석.csv).')
add('\n## 6. 실제 방문자 원문에서 월별 결합표까지')
add(f"원문: [{E['examples']['visitor']['file']}](../../{E['examples']['visitor']['file']})")
add('```json\n'+json.dumps(E['examples']['visitor']['record'],ensure_ascii=False,indent=2)+'\n```')
add(f"1. `{F('fetch_tourapi','parse_payload')}`는 XML의 items/item을 dict 목록으로 읽습니다. 값 자체는 아직 일별 자료이며, JSON도 같은 구조로 변환합니다.")
add(f'2. `{summary_ref}`는 대전 code=30, 외지인(b)을 선택하고 같은 날짜 중복, 숫자 유효성 및 달력 전체 일자 존재를 검사합니다. 위 2025-09-01의 188184.5를 포함한 30일 touNum 합계가 **7,691,190.5**입니다. 월 순방문자를 계산하는 코드가 아닙니다.')
add('3. 숙박 CSV `data/raw/20260914201051_숙박방문자 비율 추이(외지인).csv`에서 `기준연월=202509, 지역명=대전광역시, 숙박방문자 비율=14.9`를 읽습니다. 전국 광역지자체별 평균 행은 사용하지 않습니다.')
add(f'4. `{city_ref}`에서 `(region_code, month)=(30, 2025-09)`로 결합하여 `visitors=7691190.5, overnight_pct=14.9`를 기록합니다. 숙박비율을 0.149로 바꾸거나 방문자에 곱하지 않습니다.')
add('5. 후보별 11개월, 총 55행입니다. 숙박 원본 5개×24행=120행 중 후보 기간 55행 사용, 후보 2026-08 5행 제외, 전국평균 60행 제외입니다. 방문자는 11개월 일수 334일×5곳=1,670개 일별 관측치를 합산합니다. 8월 75개 일별 관측치는 제외합니다.')
add('주석 결과: [05 월별 결합표 55행](05_region_monthly_주석.csv), [06 날짜 완전성](06_visitor_coverage_주석.csv), [07 실제 일별 근거 1,745행](07_방문자_실제일별근거.csv). 원래 visitor_source에는 해당 월 전체 페이지가 들어가므로 행별 근거는 07 파일의 코드·날짜·원문 경로로 확인합니다.')
add('\n## 7. 공급 부족순위 산식과 실제 값')
add(f"`{F('analyze_pet_supply','load_demand')}`는 11개월 visitors를 산술평균합니다. 이 분석은 overnight_pct를 사용하지 않습니다. 시설 수는 분류된 고유 content_id 개수입니다.")
add('```text\n부담도 = 월평균 일반 외지인 방문자 지표 / API 등록시설 수\n시설 0개: 결과 비율은 빈칸, 내부 부담도는 inf\n백분위 = (자신보다 작은 값 개수 + (동점 개수 - 1) / 2) / (후보 수 - 1)\n부족지수 = 100 × (0.5 × 숙박 백분위 + 0.5 × 음식점 백분위)\n순위 = 1 + 자신보다 부족지수가 큰 지역 수\n```')
add('| 순위 | 지역 | 월평균 방문자 지표 | 숙박 등록 | 음식점 등록 | 숙박 백분위 | 음식점 백분위 | 부족지수 |\n|---:|---|---:|---:|---:|---:|---:|---:|')
for r in ranking:add('| '+' | '.join(r[k] for k in ['shortage_rank','region_name','mean_monthly_visitors','pet_lodging_count','pet_restaurant_count','lodging_shortage_percentile','restaurant_shortage_percentile','shortage_index'])+' |')
add('대전은 월평균 7,625,198.318182, 숙박 1개, 음식점 0개입니다. 숙박 부담도 백분위 0.75, 음식점은 전주와 함께 0개여서 공동 최댓값 0.875입니다. 따라서 `100 × (0.5 × 0.75 + 0.5 × 0.875) = 81.25`입니다. 81.25% 부족하다는 뜻이 아닙니다. [04 공급 부족순위 주석](04_pet_supply_ranking_주석.csv)에서 각 지역 계산을 확인할 수 있습니다.')
add('\n## 8. configure_tourapi_key의 실제 입력과 출력')
add(f"`{F('configure_tourapi_key','save_key')}`: 사용자가 입력한 키 문자열의 앞뒤 공백을 제거하고 빈값·내부 공백을 거부한 뒤 `.secrets/tourapi.key` 또는 `.secrets/pet_tourapi.key`에 한 줄로 저장합니다. GUI는 임시 파일에 쓴 후 교체합니다. 실제 키는 읽거나 이 검토 자료에 포함하지 않았습니다.")
add('이 파일은 API를 호출하거나 시설·방문자 데이터를 정제하지 않으므로 주석을 달 데이터 결과 CSV가 없습니다. 방문자 정제 함수는 앞 절의 fetch_tourapi.summarize_month입니다.')
add('\n## 9. 오늘 확정할 기준과 보완자료')
add('| 항목 | 현재 코드·자료의 기준 | 검토/보완할 내용 |\n|---|---|---|')
for a,b,c in [
 ('비교 지역','대전·인천·부산·강릉·전주','후보를 이 다섯 곳으로 정한 사업상 이유 기록'),
 ('행정단위','광역시 3곳 sido / 강릉·전주 sigungu의 시 전체','동일 행정 규모라고 표현하지 않기. 인구·면적 차이 검토'),
 ('공통 기간','2025-09~2026-07 11개월','8월 제외 근거 유지. 최근 자료로 갱신하려면 모든 후보 공통기간 재검사'),
 ('방문자 지표','외지인(b)의 일별 touNum 월 합계','데이터랩 월간 방문자 지표와 동일한지 공식 정의/동일 월 수치 대조 필요'),
 ('숙박비율','외지인 월별 CSV 값 그대로','수요 비교에는 쓰지만 현재 공급 부족지수에는 미사용임을 구분'),
 ('시설 시점','2026-09-19 조회 스냅샷','2025-09~2026-07 수요와 시점이 다름. 최신/과거 시설 수로 해석하지 않기'),
 ('등록 수','content_id 기준, 숙박32/음식점39','실제 업소 전수 아님. 대전·전주 음식점 0건은 공식 명부/추가 근거로 보완'),
 ('분류/중복','주소 우선, 광역시 area_code 보완; ID 중복만 제거','현재 39건 모두 주소 분류. 다른 ID의 동일 업소 중복과 주소/코드 충돌 검토'),
 ('0건 처리','부담도 inf, 비율 빈칸, 동점 중간순위','이 가정이 순위에 미치는 영향 확인'),
 ('가중치','숙박0.5 / 음식점0.5','동일 가중치 근거와 민감도 검토'),
 ('해석','일반 외지인 수요/등록시설 기반 상대 부족지수','반려견 동반 수요·실제 공급 부족률·대전 최종 선정 확정으로 과장하지 않기'),
 ('서비스 적용','목록의 이름·주소·좌표만 확보','업소별 마릿수·체중·공간/객실·영업·공식 출처/확인일 추가 조사')]:add(f'| {a} | {b} | {c} |')
add('현 코드의 주의점: `classify_place()`의 area_code 보완은 주소가 비어 있을 때만이 아니라 어떤 후보 주소에도 매칭되지 않을 때 실행됩니다. 또한 `analyze_pet_supply`는 facilities manifest의 완료 여부/해시를 스스로 확인하지 않습니다. 이번 점검에서는 별도로 완료 수집본과 해시를 확인했습니다. 코드 동작은 바꾸지 않고 주석으로 실제 조건을 설명했습니다.')
add('\n## 10. 검증과 결과 파일 읽는 법')
add('- 원문 방문자 XML 308개와 시설 JSON 10개, 총 318개의 SHA-256이 manifest와 일치했습니다.\n- 시설 원문 63행을 실제 normalise_place()로 변환한 결과가 기존 places.csv와 정확히 일치했습니다.\n- 실제 prepare_city_comparison.main()을 임시 출력 경로로 실행했고 월별 결합표 55행 및 날짜 완전성표가 기존 결과와 일치했습니다.\n- 실제 analyze_pet_supply.main()을 실행해 순위표·정제 시설표·미분류표의 모든 기존 열 값이 일치했습니다.\n- 다섯 스크립트는 주석만 추가했습니다. AST 비교로 실행 코드가 동일함을 확인했습니다.\n- 원본 WBS·기존 CSV/JSON 결과는 해시가 그대로입니다. 검토용 CSV는 원래 열/값을 그대로 두고 주석_ 열만 추가했습니다.')
add('`08_pet_supply_audit_주석.json`, `09_source_audit_주석.json`은 원본 JSON의 값은 유지하고 `_review_comments`를 추가한 검토용 사본입니다. 결과 생성 시간이 있는 과거 절대경로는 실행 당시 경로이며 현재 위치와 다를 수 있습니다. 읽기 쉬운 CSV 주석과 전체 열 설명은 이 폴더에서 확인하세요. 재현·보존 검증 내역은 `검증결과.json`에 있습니다.')
add('\n## 11. 실제 스크립트 코드 발췌')
add('아래는 설명용 의사코드가 아니라 현재 파일에서 직접 읽어 넣은 코드입니다. 전체 함수 위치는 다음 목록에 있습니다.')
def excerpt(file, start, end):
    text=(SRC/file).read_text(encoding='utf8')
    begin=text.index(start)
    finish=text.index(end,begin)+len(end)
    return text[begin:finish]
for label,file,start,end in [
    ('원문 시설 필드를 결과 열로 바꾸는 부분','fetch_pet_tourapi.py','    return {\n        "content_id":','        "source_file": source_file,\n    }'),
    ('지역별 일별 값을 더해 월별 visitors를 만드는 부분','fetch_tourapi.py','        result.append({"region_code": code','"observed_days": len(found)})'),
    ('월별 방문자와 숙박비율을 결합하는 부분','prepare_city_comparison.py','            combined.append({"region_code": code','"overnight_source": overnight_file})'),
    ('등록시설 수가 0일 때 inf로 처리하는 부분','analyze_pet_supply.py','            lodging_burden.append(math.inf','region["mean_monthly_visitors"] / item["restaurant"])'),
    ('시설 부담도를 상대 백분위로 바꾸는 부분','analyze_pet_supply.py','    return [(sum(x < value for x in values)','/ (n - 1) for value in values]'),
    ('가중 부족지수를 계산하는 부분','analyze_pet_supply.py','            index = 100 *','+ (1 - args.lodging_weight) * restaurant_pct[i])')]:
    add('\n### '+label)
    add('`'+file+'`\n\n```python\n'+excerpt(file,start,end)+'\n```')
add('\n### 코드 근거 위치')
for file,names in [('fetch_tourapi',['parse_payload','download_window','summarize_month']),('fetch_pet_tourapi',['fetch_query','normalise_place']),('analyze_pet_supply',['input_files','normalise_place','quality','classify_place','load_demand','percentile','main']),('configure_tourapi_key',['save_key','main']),('prepare_city_comparison',['find_api_folder','main'])]:
    for name in names:add('- `'+F(file,name)+'`')
(OUT/'지역선정_분석기준_점검.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
# Keep a companion annotation next to each existing result set, without altering machine inputs.
for folder in [pet_folder,supply_folder,city_folder]:
    link='../../outputs/region_review_20260924/지역선정_분석기준_점검.md' if folder.parent.name=='runs' else '../../../outputs/region_review_20260924/지역선정_분석기준_점검.md'
    (folder/'분석기준_주석.md').write_text('# 결과 데이터 주석\n\n원본 CSV/JSON 값은 보존했습니다.\n\n[실제 원문·함수·정제·집계 기준 설명]('+link+')\n\n설명 열을 붙인 결과 사본과 원래 모든 열의 설명은 `outputs/region_review_20260924/`에 있습니다.\n',encoding='utf8')
print(json.dumps({'checks':checks,'output':str(OUT)},ensure_ascii=False,indent=2))
