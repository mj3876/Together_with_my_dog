"""Fictional records isolated to demo mode. Never imported into the live database."""
from datetime import date
from app.schemas.place import Place, PetPolicy


def demo_places():
    records = []
    specs = {
        "lodging": [("포근한 마당 스테이", 36.352, 127.370), ("나란히 하우스", 36.335, 127.424)],
        "restaurant": [("한그릇 키친", 36.346, 127.377), ("초록 테이블", 36.358, 127.359),
                       ("느린 오후 식당", 36.334, 127.415), ("같이 먹는 집", 36.370, 127.389)],
        "activity": [("함께 뛰는 교실", 36.348, 127.365), ("발자국 공방", 36.360, 127.379),
                     ("교감 놀이 시간", 36.341, 127.427), ("반려견 스포츠 교실", 36.373, 127.368)],
    }
    for category, items in specs.items():
        for i, (name, lat, lon) in enumerate(items):
            records.append(Place(
                id=f"demo_{category}_{i}", venue_id=f"demo_{category}_{i}", name="[가상] " + name,
                latitude=lat, longitude=lon, address="대전광역시 · 데모용 가상 위치", category=category,
                active=True, is_demo=True, description="화면과 추천 알고리즘 확인을 위한 가상 장소입니다. 실제 방문할 수 없습니다.",
                product_name="반려견 동반 객실" if category == "lodging" else "가상 체험 프로그램" if category == "activity" else "",
                serves_meals=category == "restaurant", recurring=category == "activity",
                duration_minutes=60 if category == "activity" else None,
                participation_mode="dog_participates" if category == "activity" else "unknown",
                opens_minute=660 if category == "restaurant" else None,
                closes_minute=1200 if category == "restaurant" else None,
                schedule_note="가상 운영시간입니다. 실제 예약·방문 정보가 아닙니다.",
                policy=PetPolicy(verified=True, pet_allowed=True, max_dogs=3, max_weight_kg=25,
                                 source_url="https://example.com/demo-only", source_quote="실제 규정이 아닌 데모용 가정",
                                 checked_at=date.today(), requirements=["데모 장소: 실제 업체와 무관합니다."]),
            ))
    return records
