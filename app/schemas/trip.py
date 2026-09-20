from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Point(StrictModel):
    name: str = Field(min_length=1, max_length=160)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    @property
    def key(self):
        return f"{self.longitude:.7f},{self.latitude:.7f}"


class Location(Point):
    address: str = Field(default="", max_length=300)
    token: str = Field(default="", max_length=128)


class TripRequest(StrictModel):
    start_point: Location
    trip_days: Annotated[StrictInt, Field(ge=1)]
    dog_count: Annotated[StrictInt, Field(ge=1)]
    dog_weights_kg: list[Annotated[float, Field(gt=0)]] = Field(min_length=1)
    end_point: Location

    @field_validator("dog_weights_kg", mode="before")
    @classmethod
    def numeric_weights(cls, value):
        if not isinstance(value, list) or any(isinstance(w, (bool, str)) for w in value):
            raise ValueError("체중은 kg 숫자 배열로 입력해 주세요.")
        return value

    @model_validator(mode="after")
    def check_weights(self):
        if len(self.dog_weights_kg) != self.dog_count:
            raise ValueError("반려견 수와 체중 입력 개수가 같아야 합니다.")
        if any(abs(w * 10 - round(w * 10)) > 1e-7 for w in self.dog_weights_kg):
            raise ValueError("체중은 소수점 한 자리까지 입력해 주세요.")
        return self
