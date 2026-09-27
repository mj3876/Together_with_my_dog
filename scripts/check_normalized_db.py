"""Offline regression checks using isolated temporary databases only."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager


@contextmanager
def connect(path):
    conn = sqlite3.connect(path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()

from fastapi.testclient import TestClient
from app.core.config import Settings
from app.db.session import make_engine
from app.repositories.normalized_place_repository import catalog
from app.repositories.place_repository import all_places
from scripts.migrate_service_db import migrate, save_place, raw, source_file

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT/'outputs/policy_review_20260925'


class NormalizedChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.TemporaryDirectory()
        cls.base = Path(cls.work.name)/'base.db'
        cls.source = Path(cls.work.name)/'source.db'
        engine=make_engine(str(cls.source))
        engine.dispose()
        migrate(cls.source,REVIEW,cls.base)

    @classmethod
    def tearDownClass(cls): cls.work.cleanup()

    def setUp(self):
        self.workcase=tempfile.TemporaryDirectory()
        self.db=Path(self.workcase.name)/'normalized.db'
        with connect(self.base) as a, connect(self.db) as b: a.backup(b)

    def tearDown(self): self.workcase.cleanup()

    def snapshot(self):
        with connect(self.db) as c:
            return {t:c.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in
                ['venues','offerings','pet_policy_versions','raw_records','policy_evidence','review_issues']}

    def approved(self, **changes):
        # Fictional data exists only inside these temporary test databases.
        p=dict(id='test_meal',venue_id='test_venue',category='restaurant',name='테스트 전용 식당',
            address='대전광역시 테스트 주소',latitude=36.35,longitude=127.38,active=True,
            serves_meals=True,description='테스트 전용',schedule_note='테스트',price_note='테스트 가격',
            policy=dict(verified=True,pet_allowed=True,max_dogs=2,max_weight_kg=10,
                checked_at='2026-09-25',source_url='https://example.com/test',source_quote='테스트용 규정'))
        p.update(changes)
        return p

    def insert(self,p):
        with connect(self.db) as c:
            c.execute('PRAGMA foreign_keys=ON')
            file=source_file(c,REVIEW/'policy_review.json')
            record=raw(c,file,'/test/'+p['id'],p)
            save_place(c,p,record,approved=True)

    def test_counts_and_unknown_null(self):
        with connect(self.db) as c:
            self.assertEqual(c.execute('SELECT count(*) FROM venues').fetchone()[0],70)
            self.assertEqual(c.execute('SELECT count(*) FROM offerings').fetchone()[0],77)
            self.assertEqual(c.execute('SELECT count(*) FROM food_registrations').fetchone()[0],69)
            self.assertGreater(c.execute('SELECT count(*) FROM pet_policy_versions WHERE pet_allowed IS NULL').fetchone()[0],0)
            self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_repeat_is_idempotent_and_dry_run_does_not_write(self):
        before=self.snapshot()
        content=self.db.read_bytes()
        migrate(self.source,REVIEW,self.db,dry_run=True)
        self.assertEqual(content,self.db.read_bytes())
        migrate(self.source,REVIEW,self.db)
        self.assertEqual(before,self.snapshot())

    def test_failed_import_rolls_back_all_data(self):
        p=Path(self.workcase.name)/'approved.json'
        p.write_text(json.dumps([self.approved(),self.approved(id='bad',latitude=0)]),encoding='utf-8')
        before=self.snapshot()
        with self.assertRaises(ValueError): migrate(self.source,REVIEW,self.db,p)
        self.assertEqual(before,self.snapshot())

    def test_adapter_preserves_data_and_weight_limits(self):
        self.insert(self.approved())
        engine=make_engine(str(self.db),backend='normalized')
        try:
            p=next(p for p in all_places(engine) if p.id=='test_meal')
            self.assertTrue(p.active)
            self.assertEqual(p.price_note,'테스트 가격')
            from app.services.policy_matcher import eligible
            from types import SimpleNamespace
            self.assertTrue(eligible(p,SimpleNamespace(dog_count=2,dog_weights_kg=[10,5])))
            self.assertFalse(eligible(p,SimpleNamespace(dog_count=2,dog_weights_kg=[10.1,5])))
            self.assertFalse(eligible(p,SimpleNamespace(dog_count=3,dog_weights_kg=[5,5,5])))
        finally: engine.dispose()

    def test_required_conditions_and_dates_block_activation(self):
        p=self.approved()
        p['policy']['requirements']=['체고 40cm 미만']
        self.insert(p)
        engine=make_engine(str(self.db),backend='normalized')
        try:
            row=next(r for r in catalog(engine)[1] if r['id']=='test_meal')
            self.assertFalse(row['active'])
            self.assertIn('현재 입력으로 판정하지 못하는 필수 조건',row['reasons'])
        finally: engine.dispose()

    def test_policy_history_one_current_version(self):
        p=self.approved()
        self.insert(p)
        p['policy']['max_weight_kg']=12
        p['policy']['checked_at']='2026-09-26'
        self.insert(p)
        self.insert(p)
        with connect(self.db) as c:
            self.assertEqual(c.execute("SELECT count(*) FROM pet_policy_versions WHERE offering_id='test_meal'").fetchone()[0],2)
            self.assertEqual(c.execute("SELECT count(*) FROM pet_policy_versions WHERE offering_id='test_meal' AND is_current=1").fetchone()[0],1)

    def test_two_day_live_recommendation_with_isolated_test_catalog(self):
        from app.services.recommendation_service import recommend
        from app.schemas.trip import TripRequest, Point
        from app.schemas.itinerary import RouteLeg

        class TestRoutes:
            missing=0
            def get(self,a,b):
                return RouteLeg(origin=Point(name=a.name,latitude=a.latitude,longitude=a.longitude),
                    destination=Point(name=b.name,latitude=b.latitude,longitude=b.longitude),
                    duration_seconds=600,distance_meters=1000,route_basis='unit_test',checked_at='2026-09-27')

        for i,category in enumerate(['lodging','restaurant','restaurant','activity','activity']):
            self.insert(self.approved(id=f'test_{i}',venue_id=f'test_v_{i}',category=category,
                product_name='테스트 상품',recurring=True,duration_minutes=60,latitude=36.34+i*0.01))
        engine=make_engine(str(self.db),backend='normalized')
        try:
            trip=TripRequest(start_point=dict(name='시작',latitude=36.332,longitude=127.434),
                end_point=dict(name='종료',latitude=36.35,longitude=127.384),trip_days=2,dog_count=1,dog_weights_kg=[5])
            result=recommend(trip,engine,Settings(mode='live'),route_service=TestRoutes())
            self.assertEqual(result.status,'recommended')
            self.assertFalse(result.itinerary.is_demo)
            self.assertEqual(len(result.itinerary.days),2)
            self.assertEqual(len({d.restaurant.venue_id for d in result.itinerary.days}),2)
        finally: engine.dispose()

    def test_backend_mismatch_fails_without_legacy_table(self):
        with self.assertRaises(ValueError): make_engine(str(self.db))
        with self.assertRaises(ValueError): make_engine(str(self.source),backend='normalized')
        with connect(self.db) as c:
            self.assertIsNone(c.execute("SELECT name FROM sqlite_master WHERE name='places'").fetchone())

    def test_reference_defaults_preserve_unknown_source_facts(self):
        from scripts.prepare_reference_catalog import prepare
        from app.services.policy_matcher import eligible
        from types import SimpleNamespace
        prepare(self.db,output=Path(self.workcase.name)/'report.json')
        engine=make_engine(str(self.db),backend='normalized')
        try:
            places=all_places(engine)
            stay=next(p for p in places if p.id=='tour_3533154')
            self.assertTrue(stay.active)
            self.assertFalse(stay.policy.verified)
            self.assertFalse(stay.policy.dogs_unlimited)
            self.assertIsNone(stay.policy.max_dogs)
            self.assertTrue(eligible(stay,SimpleNamespace(dog_count=10,dog_weights_kg=[60]*10)))
            activity=next(p for p in places if p.id=='park_small_outdoor')
            self.assertTrue(activity.active)
            self.assertTrue(activity.duration_is_estimated)
            self.assertEqual(activity.duration_minutes,60)
            self.assertFalse(activity.recurring)
            self.assertTrue(activity.policy.requirements)
            with connect(self.db) as c:
                self.assertIsNone(c.execute("SELECT duration_minutes FROM offerings WHERE offering_id='park_small_outdoor'").fetchone()[0])
                self.assertEqual(c.execute("SELECT dogs_limit_state FROM pet_policy_versions WHERE offering_id='tour_3533154' AND is_current=1").fetchone()[0],'unknown')
            denied=next(p for p in places if p.id=='program_snack')
            self.assertFalse(denied.active)
            self.assertFalse(eligible(denied,SimpleNamespace(dog_count=1,dog_weights_kg=[5])))
        finally: engine.dispose()

    def test_reference_known_limits_remain_enforced(self):
        from scripts.prepare_reference_catalog import prepare
        from app.services.policy_matcher import eligible
        from types import SimpleNamespace
        self.insert(self.approved())
        prepare(self.db,output=Path(self.workcase.name)/'report.json')
        engine=make_engine(str(self.db),backend='normalized')
        try:
            p=next(p for p in all_places(engine) if p.id=='test_meal')
            self.assertTrue(eligible(p,SimpleNamespace(dog_count=2,dog_weights_kg=[10,5])))
            self.assertFalse(eligible(p,SimpleNamespace(dog_count=3,dog_weights_kg=[5]*3)))
            self.assertFalse(eligible(p,SimpleNamespace(dog_count=1,dog_weights_kg=[11])))
        finally: engine.dispose()

    def test_geocoding_requires_exact_daejeon_building(self):
        from scripts.prepare_reference_catalog import address_match
        doc={'address':{'region_1depth_name':'대전'},'road_address':{'address_name':'대전 동구 중앙로 215'},'address_name':'대전 동구 중앙로 215'}
        self.assertTrue(address_match('대전광역시 동구 중앙로 215',doc))
        self.assertFalse(address_match('대전광역시 동구 중앙로 216',doc))
        doc['address']['region_1depth_name']='서울'
        self.assertFalse(address_match('대전 동구 중앙로 215',doc))

    def test_route_prefetch_deduplicates_directed_edges_and_enforces_budget(self):
        from app.services.route_service import RouteService, RouteBudgetError
        from app.integrations.route_client import RouteError
        from app.schemas.trip import Point
        from app.schemas.itinerary import RouteLeg
        class FakeClient:
            calls=[]
            def route(self,a,b,checked_at):
                self.calls.append((a.key,b.key))
                if a.name=='b': raise RouteError('test missing route')
                return RouteLeg(origin=a,destination=b,duration_seconds=60,distance_meters=100,route_basis='unit_test',checked_at=checked_at)
            def close(self): pass
        a=Point(name='a',latitude=36.3,longitude=127.3)
        b=Point(name='b',latitude=36.4,longitude=127.4)
        routes=RouteService(Settings(mode='live',max_route_requests=2))
        routes.client=FakeClient()
        try:
            routes.prefetch([(a,b),(a,b),(b,a)])
            self.assertEqual(routes.requests,2)
            self.assertEqual(routes.missing,1)
            self.assertEqual(routes.get(a,b).duration_seconds,60)
            self.assertIsNone(routes.get(b,a))
            self.assertEqual(len(routes.client.calls),2)
        finally: routes.close()
        routes=RouteService(Settings(mode='live',max_route_requests=1))
        routes.client=FakeClient()
        try:
            with self.assertRaises(RouteBudgetError): routes.prefetch([(a,b),(b,a)])
            self.assertEqual(routes.requests,0)
        finally: routes.close()

    def test_live_app_reads_normalized_and_demo_stays_isolated(self):
        from app.main import create_app
        s=Settings(mode='live',database_path=str(self.db),database_backend='normalized',signing_key='test-only')
        with TestClient(create_app(s)) as client:
            h=client.get('/healthz').json()
            self.assertEqual(h['catalog']['total'],77)
            self.assertEqual(h['database_backend'],'normalized')
            self.assertIsNone(h['routing_connected'])
            self.assertNotIn('체험용 데모',client.get('/').text)
            p=client.get('/api/v1/places/tour_3533154').json()
            self.assertFalse(p['is_demo'])
            locations=client.get('/api/v1/locations').json()['items']
            result=client.post('/api/v1/recommendations',json=dict(start_point=locations[0],end_point=locations[1],trip_days=2,dog_count=1,dog_weights_kg=[5])).json()
            self.assertEqual(result['status'],'no_match')
        s.mode='demo'
        with TestClient(create_app(s)) as client:
            self.assertEqual(client.get('/healthz').json()['places'],10)
            self.assertIn('체험용 데모',client.get('/').text)


if __name__=='__main__': unittest.main(verbosity=2)
