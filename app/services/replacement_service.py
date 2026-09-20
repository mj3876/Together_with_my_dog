from app.core.signing import valid
from app.services.recommendation_service import recommend


def check_itinerary(itinerary, settings):
    if not valid(itinerary.model_dump(mode="json", exclude={"integrity_token"}), itinerary.integrity_token, settings.signing_key, "itinerary"):
        raise ValueError("저장된 코스 정보를 확인할 수 없습니다. 다섯 입력으로 다시 생성해 주세요.")
    if itinerary.is_demo != (settings.mode == "demo"):
        raise ValueError("데모와 실제 서비스의 코스를 섞어 사용할 수 없습니다.")


def replace(request, engine, settings):
    check_itinerary(request.itinerary, settings)
    if request.day_number > request.itinerary.request.trip_days:
        raise ValueError("여행 일차 범위를 확인해 주세요.")
    if request.slot == "lodging" and not request.itinerary.lodging_room:
        raise ValueError("당일 코스에는 교체할 숙소가 없습니다.")
    return recommend(request.itinerary.request, engine, settings, replacement=request)
