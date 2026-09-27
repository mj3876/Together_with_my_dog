"""Inspect live catalog and optionally make real Kakao calls without exposing keys."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from app.core.config import Settings
from app.db.session import make_engine
from app.services.catalog_status import catalog_status
from app.repositories.normalized_place_repository import catalog
from app.integrations.location_client import LocationClient, LocationError
from app.integrations.route_client import RouteClient, RouteError
from app.schemas.trip import Point


def check_api(settings):
    result = {}
    if not settings.kakao_key:
        result['location'] = {'status':'missing_key'}
    else:
        try:
            items = LocationClient(settings.kakao_key).search('대전역')
            result['location'] = {'status':'ok' if items else 'empty', 'results':len(items)}
        except LocationError:
            result['location'] = {'status':'failed', 'reason':'키·권한·IP·쿼터·연결 확인 필요'}
    if not settings.mobility_key:
        result['routing'] = {'status':'missing_key'}
    else:
        client = RouteClient(settings.mobility_key)
        try:
            leg = client.route(Point(name='대전역',latitude=36.332,longitude=127.434),
                Point(name='대전시청',latitude=36.3504,longitude=127.3845), datetime.now(timezone.utc).isoformat())
            result['routing'] = {'status':'ok' if leg.duration_seconds>0 and leg.distance_meters>0 else 'invalid',
                'duration_seconds':leg.duration_seconds,'distance_meters':leg.distance_meters,'basis':leg.route_basis}
        except RouteError:
            result['routing'] = {'status':'failed','reason':'키·권한·IP·쿼터·연결 확인 필요'}
        finally:
            client.close()
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path)
    parser.add_argument('--backend',choices=['normalized','legacy'],default='normalized')
    parser.add_argument('--check-api',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    settings=Settings.from_env()
    path=args.database or settings.database_path
    engine=make_engine(str(path),backend=args.backend)
    try:
        report={'database_backend':args.backend,'catalog':catalog_status(engine),
            'keys':{'location_configured':bool(settings.kakao_key),'routing_configured':bool(settings.mobility_key)},
            'api':check_api(settings) if args.check_api else {'status':'not_checked'}}
        if args.backend=='normalized': report['places']=catalog(engine)[1]
        from sqlalchemy import text
        with engine.connect() as conn:
            report['integrity']=conn.execute(text('PRAGMA integrity_check')).scalar()
            report['foreign_key_errors']=len(conn.execute(text('PRAGMA foreign_key_check')).all())
        counts=report['catalog']['active_by_category']
        report['minimum_catalog_for_two_days']=all(counts.get(k,0)>=n for k,n in [('lodging',1),('restaurant',2),('activity',2)])
        report['note']='최소 수량 통과는 특정 반려견 조건·일정에서의 추천 성공을 보장하지 않습니다.'
        output=json.dumps(report,ensure_ascii=False,indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(output,encoding='utf-8')
        print(output)
    finally:
        engine.dispose()


if __name__=='__main__': main()
