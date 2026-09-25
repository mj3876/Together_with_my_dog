import ast
import contextlib
import csv
import hashlib
import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Together_with_my_dog_cityselection'))
import fetch_tourapi as visitor
import fetch_pet_tourapi as pet
import prepare_city_comparison as city
import analyze_pet_supply as supply

OUT = ROOT / 'tmp/region_review_20260924'
OUT.mkdir(exist_ok=True)
def read_csv(p):
    with p.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

sources = ['fetch_tourapi.py', 'fetch_pet_tourapi.py', 'analyze_pet_supply.py', 'configure_tourapi_key.py', 'prepare_city_comparison.py']
save('before_ast.json', {name: ast.dump(ast.parse((ROOT / 'Together_with_my_dog_cityselection' / name).read_text(encoding='utf-8'))) for name in sources})
protected = [ROOT/'region_monthly.csv', *list((ROOT/'data/processed/city_202509_202607').glob('*')), *list((ROOT/'runs/pet_supply_20260919_184024').glob('*')), ROOT/'outputs/wbs_20260924_0930/우리개와끝까지함께_WBS_0924-0930.xlsx']
save('protected_sha.json', {str(p.relative_to(ROOT)): sha(p) for p in protected if p.is_file()})
folders = [ROOT/'runs/api_candidates_sido_202509_202608', ROOT/'runs/api_candidates_sigungu_202509_202608', ROOT/'runs/pet_api_20260919_183904']
info = []
daily = []
raw_examples = {}
for folder in folders:
    m = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    rows = []
    hashes = 0
    for page in m['pages']:
        p = folder/page['file']
        assert sha(p) == page['sha256'], str(p)
        hashes += 1
        records, total, actual_page, size = visitor.parse_payload(p.read_bytes())
        assert len(records) == page['rows']
        for r in records:
            rows.append(r)
            if m.get('level'):
                code = r['areaCode'] if m['level']=='sido' else r['signguCode']
                if str(code) in {'30','28','26','51150','52110'} and r['touDivNm']=='외지인(b)':
                    daily.append({'region_code':code, 'month':r['baseYmd'][:4]+'-'+r['baseYmd'][4:6], 'baseYmd':r['baseYmd'], 'touNum':r['touNum'], 'source_file':str(p.relative_to(ROOT)).replace('\\','/')})
                    if code=='30' and r['baseYmd']=='20250901':
                        raw_examples['visitor'] = {'file':str(p.relative_to(ROOT)).replace('\\','/'), 'record':r}
    fields = sorted({k for row in rows for k in row})
    item = {k:v for k,v in m.items() if k not in {'pages','authenticated_key_supplied'}}
    item.update(folder=str(folder.relative_to(ROOT)).replace('\\','/'), files=len(m['pages']), extensions=dict(Counter(Path(p['file']).suffix for p in m['pages'])), actual_rows=len(rows), fields=fields, verified_hashes=hashes)
    if m.get('level'):
        item['visitor_types']=dict(Counter(r['touDivNm'] for r in rows))
    info.append(item)
    if 'pet_api' in folder.name:
        raw_examples['pet']={'file':str((folder/'raw/q03_p0001.json').relative_to(ROOT)).replace('\\','/'), 'record':visitor.parse_payload((folder/'raw/q03_p0001.json').read_bytes())[0][0]}
        recreated=[]
        for q in m['queries']:
            for file in q['files']:
                records,*_ = visitor.parse_payload((folder/file).read_bytes())
                recreated.extend(pet.normalise_place(r, query_area_code=q['area_code'], query_content_type_id=q['content_type_id'], source_file=';'.join(q['files'])) for r in records)
        assert recreated == read_csv(folder/'places.csv')
        assert sha(folder/'places.csv') == m['places_sha256']

# Execute the actual preparation main, redirecting only its output and root copy.
# All raw inputs stay at the original project paths; no network calls are used.
real_path = Path
city.OUTPUT = OUT/'replayed_city'
city.Path = lambda value: OUT/'replayed_region_monthly.csv' if str(value)=='region_monthly.csv' else real_path(value)
with contextlib.redirect_stdout(io.StringIO()):
    city.main()
for name in ['region_monthly.csv','visitor_coverage.csv']:
    assert read_csv(city.OUTPUT/name) == read_csv(ROOT/'data/processed/city_202509_202607'/name), name
with contextlib.redirect_stdout(io.StringIO()):
    supply.main(['--input', str(folders[2]), '--demand', str(ROOT/'data/processed/city_202509_202607/region_monthly.csv'), '--output', str(OUT/'replayed_supply')])
for name in ['pet_supply_ranking.csv','pet_facilities_deduplicated.csv','unmatched_places.csv']:
    assert read_csv(OUT/'replayed_supply'/name) == read_csv(ROOT/'runs/pet_supply_20260919_184024'/name), name

unmatched=read_csv(OUT/'replayed_supply/unmatched_places.csv')
coverage_aug=defaultdict(set)
for r in daily:
    if r['month']=='2026-08': coverage_aug[r['region_code']].add(r['baseYmd'])
save('evidence.json', {'folders':info, 'examples':raw_examples,
     'checks':{'raw_pages_hash_verified':sum(x['files'] for x in info), 'pet_raw_to_places_exact':True, 'city_55_rows_exact':True,'city_coverage_exact':True,'supply_three_csv_exact':True},
     'august_days':{k:{'days':len(v),'first':min(v),'last':max(v)} for k,v in coverage_aug.items()},
     'unmatched_address_prefixes':dict(Counter(' '.join(r['addr1'].split()[:2]) for r in unmatched)),
     'pet_classification_methods':dict(Counter(r['classification_method'] for r in read_csv(OUT/'replayed_supply/pet_facilities_deduplicated.csv'))),
     'daily':daily})
print(json.dumps({'folders':[{k:x.get(k) for k in ['folder','status','files','extensions','actual_rows','fields','error']} for x in info], 'examples':raw_examples, 'checks':'all exact', 'unmatched_address_prefixes':dict(Counter(' '.join(r['addr1'].split()[:2]) for r in unmatched))}, ensure_ascii=False, indent=2))
