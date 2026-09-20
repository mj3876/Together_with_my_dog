from fastapi import APIRouter, HTTPException, Request
from app.schemas.itinerary import ReplaceRequest, InquiryRequest
from app.schemas.recommendation import Recommendation
from app.services.replacement_service import replace, check_itinerary
from app.services.inquiry_service import inquiry

router = APIRouter(prefix="/api/v1/itineraries")


@router.post("/replace", response_model=Recommendation)
def replace_itinerary(body: ReplaceRequest, request: Request):
    state = request.app.state
    if not state.planning_slots.acquire(blocking=False):
        raise HTTPException(503, "코스를 계산 중입니다. 잠시 후 다시 시도해 주세요.")
    try:
        return replace(body, state.engine, state.settings)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    finally:
        state.planning_slots.release()


@router.post("/inquiry")
def make_inquiry(body: InquiryRequest, request: Request):
    try:
        check_itinerary(body.itinerary, request.app.state.settings)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return {"messages": inquiry(body.itinerary)}
