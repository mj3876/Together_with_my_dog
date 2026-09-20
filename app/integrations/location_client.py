import httpx


class LocationError(Exception):
    pass


class LocationClient:
    BASE = "https://dapi.kakao.com/v2/local"

    def __init__(self, key):
        self.key = key

    def get(self, endpoint, params):
        if not self.key:
            raise LocationError("장소 검색 연결이 아직 준비되지 않았습니다. 아래 출발 지점을 선택해 주세요.")
        try:
            with httpx.Client(timeout=8, follow_redirects=False) as client:
                response = client.get(self.BASE + endpoint, params=params, headers={"Authorization": "KakaoAK " + self.key})
                response.raise_for_status()
                return response.json()["documents"]
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            raise LocationError("장소 검색에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.") from None

    def search(self, query):
        places = self.get("/search/keyword.json", {"query": query if "대전" in query else "대전 " + query, "size": 15})
        results = []
        for p in places:
            address = p.get("address_name", "")
            if address.startswith(("대전 ", "대전광역시 ")):
                results.append(dict(name=p["place_name"], address=address, latitude=float(p["y"]), longitude=float(p["x"])))
        if not results:
            for p in self.get("/search/address.json", {"query": query, "size": 10}):
                address = p.get("address") or {}
                if address.get("region_1depth_name") in {"대전", "대전광역시"}:
                    results.append(dict(name=p["address_name"], address=p["address_name"], latitude=float(p["y"]), longitude=float(p["x"])))
        return results[:10]

    def resolve(self, latitude, longitude):
        regions = self.get("/geo/coord2regioncode.json", {"x": longitude, "y": latitude})
        region = next((p for p in regions if p.get("region_type") == "B"), None)
        if not region or region.get("region_1depth_name") not in {"대전", "대전광역시"}:
            raise LocationError("출발과 종료 위치는 대전 안에서 선택해 주세요.")
        return dict(name="선택한 위치", address=region["address_name"], latitude=latitude, longitude=longitude)
