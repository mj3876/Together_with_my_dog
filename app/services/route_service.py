from datetime import datetime, timezone
import hashlib
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from app.integrations.route_client import RouteClient, RouteError
from app.schemas.itinerary import RouteLeg
from app.schemas.trip import Point


class RouteBudgetError(Exception):
    pass


class RouteService:
    """Directed, request-scoped cache. Never invent a live route or persist provider data."""
    def __init__(self, settings):
        self.settings = settings
        self.cache = {}
        self.requests = 0
        self.missing = 0
        self.checked_at = datetime.now(timezone.utc).isoformat()
        self.deadline = time.monotonic() + 40
        self.client = RouteClient(settings.mobility_key) if settings.mode == "live" and settings.mobility_key else None

    def close(self):
        if self.client:
            self.client.close()

    def prefetch(self, pairs):
        """Fetch unique directed edges concurrently within this request's budget."""
        if not self.client:
            return
        pending = {}
        for origin,destination in pairs:
            key=(origin.key,destination.key)
            if key in self.cache or key in pending:
                continue
            if origin.key == destination.key:
                self.get(origin,destination)
            else:
                pending[key]=(origin,destination)
        if len(pending)+self.requests > self.settings.max_route_requests:
            raise RouteBudgetError('전체 후보의 경로 수가 조회 한도를 초과했습니다.')
        remaining=self.deadline-time.monotonic()
        if remaining<=0:
            raise RouteBudgetError('경로 조회 시간 한도에 도달했습니다.')

        def fetch(pair):
            # Client is shared across threads; only the calling thread mutates cache/counters.
            a,b=pair
            try:
                return self.client.route(a,b,self.checked_at)
            except RouteError:
                return None

        self.requests += len(pending)
        executor=ThreadPoolExecutor(max_workers=6)
        futures={executor.submit(fetch,pair):key for key,pair in pending.items()}
        try:
            for future in as_completed(futures,timeout=remaining):
                route=future.result()
                self.cache[futures[future]]=route
                if route is None: self.missing+=1
        except TimeoutError:
            raise RouteBudgetError('경로 조회 시간 한도에 도달했습니다. 다시 시도해 주세요.') from None
        finally:
            for future in futures: future.cancel()
            executor.shutdown(wait=True,cancel_futures=True)

    def get(self, origin, destination):
        key = (origin.key, destination.key)
        if key in self.cache:
            return self.cache[key]
        if self.requests >= self.settings.max_route_requests or time.monotonic() > self.deadline:
            raise RouteBudgetError("경로 조회 한도에 도달했습니다. 데이터 범위를 정리한 뒤 다시 계산해 주세요.")
        self.requests += 1
        a = Point(**origin.model_dump(include={"name", "latitude", "longitude"}))
        b = Point(**destination.model_dump(include={"name", "latitude", "longitude"}))
        route = None
        if a.key == b.key:
            route = RouteLeg(origin=a, destination=b, duration_seconds=0, distance_meters=0,
                             route_basis="same_location", checked_at=self.checked_at)
        elif self.settings.mode == "demo":
            # Deliberately synthetic. Not a road routing fallback.
            length = math.hypot((a.latitude - b.latitude) * 111000, (a.longitude - b.longitude) * 89000)
            offset = int(hashlib.sha256((a.key + b.key).encode()).hexdigest()[:4], 16) % 180
            route = RouteLeg(origin=a, destination=b, duration_seconds=round(length / 9) + 120 + offset,
                             distance_meters=round(length * 1.25), route_basis="demo_synthetic_NOT_ROAD",
                             checked_at=self.checked_at)
        elif self.client:
            try:
                route = self.client.route(a, b, self.checked_at)
            except RouteError:
                pass
        if route is None:
            self.missing += 1
        self.cache[key] = route
        return route
