from datetime import date
from typing import Literal
from pydantic import Field, HttpUrl, model_validator
from app.schemas.trip import Point, StrictModel


class PetPolicy(StrictModel):
    verified: bool = False
    pet_allowed: bool = False
    max_dogs: int | None = Field(default=None, ge=1)
    dogs_unlimited: bool = False
    max_weight_kg: float | None = Field(default=None, gt=0)
    weight_unlimited: bool = False
    weight_operator: Literal["lte", "lt"] = "lte"
    requirements: list[str] = Field(default_factory=list)
    source_url: HttpUrl | None = None
    source_quote: str = ""
    checked_at: date | None = None

    @model_validator(mode="after")
    def limits_consistent(self):
        if self.dogs_unlimited and self.max_dogs is not None:
            raise ValueError("마릿수 제한과 무제한을 동시에 지정할 수 없습니다.")
        if self.weight_unlimited and self.max_weight_kg is not None:
            raise ValueError("체중 제한과 무제한을 동시에 지정할 수 없습니다.")
        if self.verified and (not self.source_url or not self.source_quote or not self.checked_at):
            raise ValueError("확인된 규정에는 출처 URL·근거·확인일이 필요합니다.")
        return self


class Place(Point):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,100}$")
    venue_id: str = Field(min_length=1, max_length=100)
    category: Literal["lodging", "restaurant", "activity"]
    address: str = Field(min_length=1)
    description: str = ""
    active: bool = False
    policy: PetPolicy = Field(default_factory=PetPolicy)
    product_name: str = ""
    serves_meals: bool = False
    participation_mode: Literal["dog_participates", "accompany", "unknown"] = "unknown"
    recurring: bool = False
    duration_minutes: int | None = Field(default=None, gt=0)
    # Generic, date-independent opening window only. Weekly exceptions stay in notes.
    opens_minute: int | None = Field(default=None, ge=0, le=1439)
    closes_minute: int | None = Field(default=None, ge=1, le=1440)
    checkin_minute: int = Field(default=900, ge=0, le=1439)
    checkout_minute: int = Field(default=660, ge=0, le=1439)
    schedule_note: str = "방문 날짜의 운영시간·예약 여부를 확인해 주세요."
    official_url: HttpUrl | None = None
    price_note: str = ""
    is_demo: bool = False

    @model_validator(mode="after")
    def schedule_window(self):
        if (self.opens_minute is None) != (self.closes_minute is None):
            raise ValueError("일반 영업 구간은 시작과 종료를 함께 입력합니다.")
        if self.opens_minute is not None and self.opens_minute >= self.closes_minute:
            raise ValueError("자정 통과 영업은 schedule_note에 기록합니다.")
        return self
