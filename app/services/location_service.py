from app.schemas.trip import Location
from app.core.signing import sign, valid
from app.integrations.location_client import LocationClient, LocationError

# Public arrival landmarks, not recommended dog-friendly businesses.
PRESETS = [
    dict(name="대전역", address="대전광역시 동구 중앙로 215", latitude=36.332, longitude=127.434),
    dict(name="유성온천역", address="대전광역시 유성구 계룡로 지하 97", latitude=36.3537, longitude=127.3415),
    dict(name="대전시청", address="대전광역시 서구 둔산로 100", latitude=36.3504, longitude=127.3845),
]


def signed_location(data, settings):
    loc = Location.model_validate(data)
    loc.token = sign(loc.model_dump(exclude={"token"}), settings.signing_key, "location")
    return loc


def verify_location(location, settings):
    if not valid(location.model_dump(exclude={"token"}), location.token, settings.signing_key, "location"):
        raise LocationError("검색 결과에서 위치를 다시 선택해 주세요.")


def search_locations(query, settings):
    presets = [p for p in PRESETS if not query or query in p["name"] or query in p["address"]]
    if query and settings.kakao_key:
        remote = LocationClient(settings.kakao_key).search(query)
    else:
        remote = []
    unique = {f'{p["longitude"]},{p["latitude"]}': p for p in [*presets, *remote]}
    return [signed_location(p, settings) for p in unique.values()]
