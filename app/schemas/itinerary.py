from typing import Literal
from pydantic import Field
from app.schemas.trip import StrictModel, Point, TripRequest
from app.schemas.place import Place


class RouteLeg(StrictModel):
    origin: Point
    destination: Point
    duration_seconds: int = Field(ge=0)
    distance_meters: int = Field(ge=0)
    route_basis: str
    checked_at: str
    geometry: list[list[float]] = Field(default_factory=list)


class Stop(StrictModel):
    place: Place
    arrival_minute: float
    start_minute: float
    end_minute: float
    wait_minutes: float = 0


class DayPlan(StrictModel):
    day_number: int
    start_point: Point
    end_point: Point
    restaurant: Place
    activity: Place
    stops: list[Stop]
    route_legs: list[RouteLeg]
    start_minute: float
    end_minute: float
    estimated_duration_seconds: int
    total_drive_seconds: int
    max_leg_seconds: int
    lodging_wait_minutes: float = 0


class Itinerary(StrictModel):
    request: TripRequest
    nights: int
    lodging_room: Place | None
    days: list[DayPlan]
    total_drive_seconds: int
    max_leg_seconds: int
    planning_basis: list[str]
    reasons: list[str]
    visit_requirements: list[str]
    policy_checks: str = "입력한 반려견 수·각 체중 조건 일치. 기타 조건은 방문 전 확인."
    schedule_status: str = "date_unspecified"
    booking_status: str = "not_checked"
    is_demo: bool = False
    # Signed server context: replacement/inquiry never trust client-supplied suitability.
    integrity_token: str = ""


class ReplaceRequest(StrictModel):
    itinerary: Itinerary
    slot: Literal["lodging", "restaurant", "activity"]
    day_number: int = Field(default=1, ge=1)


class InquiryRequest(StrictModel):
    itinerary: Itinerary
