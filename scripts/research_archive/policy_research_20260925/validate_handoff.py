import hashlib
import json
import sqlite3
from pathlib import Path
from app.schemas.place import Place
from scripts.build_service_db import import_catalog

OUT=Path('outputs/policy_review_20260925')
def read(name):
    return json.loads((OUT/name).read_text(encoding='utf-8'))
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

original_db_sha=sha('data/app.db')
records=read('places_import_inactive.json')
places=[Place.model_validate(x) for x in records]
assert len(places)==9 and len({p.id for p in places})==9
assert all(not p.active and not p.policy.verified and not p.is_demo for p in places)
assert all(not p.policy.dogs_unlimited and not p.policy.weight_unlimited for p in places)
assert all(p.policy.max_dogs is None and p.policy.max_weight_kg is None for p in places)
registrations=read('restaurant_registrations.json')
candidates=read('restaurant_candidates.json')
assert len(registrations)==69 and len(candidates)==68
assert {r['venue_id'] for r in registrations}=={r['venue_id'] for r in candidates}
assert sum(len(x['registration_ids']) for x in candidates)==69
kong=[r for r in candidates if r['name']=='콩월']
assert len(kong)==1 and len(kong[0]['registration_ids'])==2
assert len({r['registration_id'] for r in registrations})==69
assert all(x['name'] and x['address'] for x in registrations)
assert all(x['latitude'] is None and not x['active'] for x in candidates)
for evidence in read('sources.json'):
    if evidence.get('file'):
        assert sha(OUT/evidence['file'])==evidence['sha256']

test_db='tmp/policy_research_20260925/handoff_check.db'
assert import_catalog([OUT/'places_import_inactive.json'],test_db)==9
with sqlite3.connect(test_db) as app_db:
    assert app_db.execute('SELECT count(*) FROM places').fetchone()[0]==9
    assert app_db.execute("SELECT count(*) FROM places WHERE json_extract(document,'$.active')=1").fetchone()[0]==0
assert sha('data/app.db')==original_db_sha

db=sqlite3.connect(':memory:')
db.executescript(Path('docs/database_schema.sql').read_text(encoding='utf-8'))
tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
assert len(tables)==22
assert db.execute('PRAGMA foreign_keys').fetchone()[0]==1
db.execute("INSERT INTO data_sources VALUES ('s','fixture','fixture','official_file',NULL,'')")
db.execute("INSERT INTO ingestion_runs VALUES ('run','s','2026-09-25','complete','{}','')")
db.execute("INSERT INTO source_files VALUES ('f','run','fixture.json',?,'json',NULL,NULL)",('0'*64,))
db.execute("INSERT INTO raw_records VALUES ('raw','f','row1',NULL,'{}')")
db.execute("INSERT INTO regions(region_id,name,level) VALUES ('r','대전광역시','sido')")
db.execute("INSERT INTO venues(venue_id,name,address) VALUES ('v','fixture','대전광역시 유성구')")
db.execute("INSERT INTO offerings(offering_id,venue_id,name,category,scope_type) VALUES ('o','v','fixture','activity','space')")
db.execute("INSERT INTO pet_policy_versions(policy_id,offering_id,checked_at,review_status) VALUES ('p','o','2026-09-25','partial')")
assert db.execute("SELECT pet_allowed,max_dogs,max_weight_kg FROM pet_policy_versions").fetchone()==(None,None,None)
rejected=[]
def reject(label,sql):
    try:
        db.execute(sql)
    except sqlite3.IntegrityError:
        rejected.append(label)
    else:
        raise AssertionError(label+' was accepted')

reject('foreign_key_orphan',"INSERT INTO offerings(offering_id,venue_id,name,category,scope_type) VALUES ('bad','missing','x','activity','space')")
reject('second_current_policy',"INSERT INTO pet_policy_versions(policy_id,offering_id,checked_at,review_status) VALUES ('p2','o','2026-09-25','partial')")
reject('unlimited_and_numeric_dog_limit',"UPDATE pet_policy_versions SET dogs_limit_state='unlimited',max_dogs=2 WHERE policy_id='p'")
reject('limited_without_numeric_weight',"UPDATE pet_policy_versions SET weight_limit_state='limited',weight_operator='lte' WHERE policy_id='p'")
reject('complete_month_missing_days',"INSERT INTO regional_monthly_metrics VALUES ('m','run','r','2026-08','b',123,10,15,31,'complete')")
reject('out_of_range_overnight_pct',"INSERT INTO regional_monthly_metrics VALUES ('m2','run','r','2026-08','b',123,101,15,31,'incomplete')")
reject('reversed_schedule_interval',"INSERT INTO schedule_exceptions VALUES ('e','o','2026-09-27T00:00','2026-09-24T00:00','closed',NULL,NULL,'x','raw')")
reject('null_primary_key',"INSERT INTO venues(venue_id,name,address) VALUES (NULL,'x','대전')")
db.execute("INSERT INTO policy_conditions VALUES ('height','p','height_cm','lt','40','cm','manual','체고 40cm 미만','raw')")
assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
assert not db.execute('PRAGMA foreign_key_check').fetchall()
db.close()
result=dict(checked_at='2026-09-25',restaurant_registrations=69,restaurant_venues=68,
    inactive_places_validated_and_test_imported=9,active_places=0,ddl_tables_created=len(tables),
    constraint_rejections_passed=rejected,source_hashes_verified=True,existing_app_db_unchanged=True,
    original_app_db_sha256=original_db_sha,
    schema_sql_sha256=sha('docs/database_schema.sql'),
    places_import_sha256=sha(OUT/'places_import_inactive.json'),
    limitations=['정규화 스키마의 전체 데이터 ETL 및 앱 어댑터 미구현','실제 업체 전화 확인·운영 승인 미실시','원본 WBS 상태 미변경'])
(OUT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
