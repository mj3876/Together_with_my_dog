"""Apply requested reference-planning rules without rewriting source policy facts."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3

from app.core.config import Settings
from app.db.normalized import initialize
from app.integrations.location_client import LocationClient, LocationError
from scripts.migrate_service_db import source_file, raw


def address_query(address):
    return re.split(r'[(,]',address)[0].strip()


def normalized_address(address):
    return re.sub(r'\s+','',address.replace('대전광역시','대전'))


def address_match(query, document):
    road=document.get('road_address') or {}
    address=document.get('address') or {}
    if address.get('region_1depth_name') not in {'대전','대전광역시'}:
        return False
    # Require the exact street/building address, not merely a district or street centroid.
    expected=normalized_address(query)
    return any(expected==normalized_address(x) for x in [road.get('address_name',''),document.get('address_name','')])


def prepare(database, geocode=False, minutes=60, output=Path('data/live_transition/reference_preparation.json')):
    settings=Settings.from_env()
    client=LocationClient(settings.kakao_key)
    if geocode and not settings.kakao_key:
        raise ValueError('KAKAO_REST_API_KEY를 입력하세요.')
    conn=sqlite3.connect(database)
    conn.row_factory=sqlite3.Row
    report={'geocoded':[],'unresolved':[],'reference_enabled':0,'activity_default_minutes':minutes}
    try:
        initialize(conn)
        if geocode:
            rows=conn.execute('SELECT venue_id,name,address FROM venues WHERE latitude IS NULL OR longitude IS NULL ORDER BY venue_id').fetchall()
            for row in rows:
                query=address_query(row['address'])
                try:
                    docs=client.get('/search/address.json',{'query':query,'analyze_type':'exact','size':30})
                except LocationError:
                    raise ValueError('카카오 주소 검색 실패. 키·권한·네트워크를 확인하세요.') from None
                matches=[d for d in docs if address_match(query,d)]
                locations={(d['x'],d['y']) for d in matches}
                if len(locations)!=1:
                    report['unresolved'].append({'id':row['venue_id'],'name':row['name'],'address':row['address'],'reason':'정확한 단일 주소 결과 없음'})
                    continue
                lon,lat=map(float,next(iter(locations)))
                if not (36.1<lat<36.55 and 127.2<lon<127.65):
                    report['unresolved'].append({'id':row['venue_id'],'reason':'대전 권역 밖 좌표'})
                    continue
                path=Path('data/live_transition/geocoding')/(row['venue_id']+'.json')
                path.parent.mkdir(parents=True,exist_ok=True)
                payload={'provider':'kakao_local_address','queried_at':datetime.now(timezone.utc).isoformat(),
                         'query':query,'documents':docs}
                path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
                with conn:
                    fid=source_file(conn,path,'https://developers.kakao.com/docs/ko/local/dev-guide')
                    rid=raw(conn,fid,'/documents',matches,row['venue_id'])
                    conn.execute('UPDATE venues SET latitude=?,longitude=?,location_record_id=? WHERE venue_id=?',(lat,lon,rid,row['venue_id']))
                report['geocoded'].append(row['venue_id'])
                print(f'Address resolved: {row["venue_id"]}',flush=True)
        with conn:
            # Keep explicitly denied/unknown pet participation out. Incomplete limits
            # become a planning default, not a verified unlimited venue policy.
            rows=conn.execute("""SELECT o.offering_id FROM offerings o
              JOIN pet_policy_versions p ON p.offering_id=o.offering_id AND p.is_current=1
              WHERE p.pet_allowed=1 AND p.review_status NOT IN ('conflict','rejected')""").fetchall()
            for row in rows:
                conn.execute('INSERT INTO reference_planning VALUES (?,?,?,?,?) ON CONFLICT(offering_id) DO UPDATE SET enabled=1,activity_minutes=excluded.activity_minutes',
                    (row['offering_id'],1,minutes,datetime.now(timezone.utc).isoformat(),
                     '사용자 요청: 미확인 제한은 추천에서 제외하지 않고 부족한 상세 정보는 추가 입력 없이 참고 계획에 반영. 원본 규정은 유지.'))
            report['reference_enabled']=len(rows)
        output=Path(output)
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        return report
    finally:
        conn.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,default=Path('data/app_normalized.db'))
    parser.add_argument('--geocode',action='store_true')
    parser.add_argument('--activity-minutes',type=int,default=60)
    args=parser.parse_args()
    if args.activity_minutes<=0: parser.error('체험 기본 시간은 양수여야 합니다.')
    if not args.database.is_file(): parser.error('정규화 DB가 없습니다.')
    print(json.dumps(prepare(args.database,args.geocode,args.activity_minutes),ensure_ascii=False,indent=2))


if __name__=='__main__': main()
