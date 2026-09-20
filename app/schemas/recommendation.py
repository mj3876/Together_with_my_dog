from typing import Literal
from app.schemas.trip import StrictModel
from app.schemas.itinerary import Itinerary


class Recommendation(StrictModel):
    status: Literal["recommended", "no_match", "route_unavailable", "planning_limit"]
    itinerary: Itinerary | None = None
    reasons: list[str]
