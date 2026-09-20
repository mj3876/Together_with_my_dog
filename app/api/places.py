from fastapi import APIRouter, HTTPException, Query, Request
from app.repositories.place_repository import get_place
from app.services.location_service import search_locations, signed_location
from app.integrations.location_client import LocationClient, LocationError

router = APIRouter(prefix="/api/v1")


@router.get("/places/{place_id}")
def detail(place_id: str, request: Request):
    place = get_place(request.app.state.engine, place_id)
    if place is None:
        raise HTTPException(404, "장소를 찾을 수 없습니다.")
    return place


@router.get("/locations")
def locations(request: Request, q: str = Query(default="", max_length=100)):
    settings = request.app.state.settings
    try:
        return {"items": search_locations(q.strip(), settings), "search_connected": bool(settings.kakao_key)}
    except LocationError as exc:
        raise HTTPException(503, str(exc)) from None


@router.get("/locations/resolve")
def resolve(request: Request, latitude: float = Query(ge=-90, le=90), longitude: float = Query(ge=-180, le=180)):
    settings = request.app.state.settings
    try:
        point = LocationClient(settings.kakao_key).resolve(latitude, longitude)
        return signed_location(point, settings)
    except LocationError as exc:
        raise HTTPException(422, str(exc)) from None
