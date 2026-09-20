import httpx
from app.schemas.itinerary import RouteLeg
from app.schemas.trip import Point


class RouteError(Exception):
    pass


class RouteClient:
    def __init__(self, key):
        self.client = httpx.Client(timeout=6, follow_redirects=False, headers={"Authorization": "KakaoAK " + key})

    def close(self):
        self.client.close()

    def route(self, origin, destination, checked_at):
        try:
            response = self.client.get("https://apis-navi.kakaomobility.com/v1/directions", params={
                "origin": f"{origin.longitude},{origin.latitude}",
                "destination": f"{destination.longitude},{destination.latitude}", "priority": "TIME",
                "alternatives": "false", "road_details": "true",
            })
            response.raise_for_status()
            route = response.json()["routes"][0]
            if route["result_code"] != 0:
                raise RouteError("이동 경로 없음")
            summary = route["summary"]
            coordinates = []
            for section in route.get("sections", []):
                for road in section.get("roads", []):
                    vertexes = road.get("vertexes", [])
                    coordinates.extend([[vertexes[i + 1], vertexes[i]] for i in range(0, len(vertexes) - 1, 2)])
            return RouteLeg(origin=Point(**origin.model_dump(include={"name", "latitude", "longitude"})),
                            destination=Point(**destination.model_dump(include={"name", "latitude", "longitude"})),
                            duration_seconds=summary["duration"], distance_meters=summary["distance"],
                            route_basis="kakao_current_TIME", checked_at=checked_at, geometry=coordinates)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
            raise RouteError("경로 정보를 가져오지 못했습니다.") from None
