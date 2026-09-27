"""Live HTTP smoke test via TestClient; uses real Kakao routing and saves a local report."""
import argparse
import json
from pathlib import Path
import time
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import create_app


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days',type=int,default=2)
    parser.add_argument('--output',type=Path,default=Path('data/live_transition/live_reference_smoke.json'))
    args=parser.parse_args()
    settings=Settings.from_env()
    if settings.mode!='live': raise SystemExit('APP_MODE must be live')
    started=time.monotonic()
    with TestClient(create_app(settings)) as client:
        health=client.get('/healthz').json()
        points=client.get('/api/v1/locations').json()['items']
        result=client.post('/api/v1/recommendations',json=dict(start_point=points[0],end_point=points[1],
            trip_days=args.days,dog_count=2,dog_weights_kg=[5,20])).json()
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps({'health':health,'result':result,'elapsed_seconds':time.monotonic()-started},ensure_ascii=False,indent=2),encoding='utf-8')
        itinerary=result.get('itinerary') or {}
        print(json.dumps({'status':result.get('status'),'reasons':result.get('reasons'),
            'catalog':health['catalog'],'days':len(itinerary.get('days',[])),
            'elapsed_seconds':round(time.monotonic()-started,2),
            'route_bases':sorted({leg['route_basis'] for day in itinerary.get('days',[]) for leg in day['route_legs']})},ensure_ascii=False,indent=2))
        if result.get('status')!='recommended': raise SystemExit(1)
        inquiry=client.post('/api/v1/itineraries/inquiry',json={'itinerary':itinerary})
        assert inquiry.status_code==200, inquiry.status_code
        print('Signed itinerary inquiry check: ok')


if __name__=='__main__': main()
