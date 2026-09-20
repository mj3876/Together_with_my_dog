from fastapi import APIRouter, HTTPException, Request
from app.schemas.trip import TripRequest
from app.schemas.recommendation import Recommendation
from app.services.location_service import verify_location
from app.integrations.location_client import LocationError
from app.services.recommendation_service import recommend

router = APIRouter(prefix="/api/v1")


@router.post("/recommendations", response_model=Recommendation)
def recommendations(body: TripRequest, request: Request):
    state = request.app.state
    try:
        verify_location(body.start_point, state.settings)
        verify_location(body.end_point, state.settings)
    except LocationError as exc:
        raise HTTPException(422, str(exc)) from None
    if not state.planning_slots.acquire(blocking=False):
        raise HTTPException(503, "다른 코스를 계산 중입니다. 잠시 후 다시 시도해 주세요.")
    try:
        return recommend(body, state.engine, state.settings)
    finally:
        state.planning_slots.release()
