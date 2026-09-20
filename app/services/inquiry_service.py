def inquiry(itinerary):
    weights = ", ".join(f"{w:g}kg" for w in itinerary.request.dog_weights_kg)
    places = ([itinerary.lodging_room] if itinerary.lodging_room else [])
    places += [s.place for d in itinerary.days for s in d.stops]
    result = []
    for place in {p.id: p for p in places}.values():
        body = (f"안녕하세요. {place.name} 이용을 문의드립니다.\n"
                f"반려견 {itinerary.request.dog_count}마리, 체중은 {weights}입니다.\n"
                f"이용 상품: {place.product_name or '반려견 동반 식사'}\n"
                "방문 날짜와 인원을 정한 뒤 예약 가능 여부를 확인하려고 합니다.\n"
                "현재 동반 규정, 준비물, 이용 공간과 운영시간을 알려주세요.")
        if place.policy.requirements:
            body += "\n추가 확인사항: " + " / ".join(place.policy.requirements)
        if itinerary.is_demo:
            body = "[데모 예시: 실제 업체에 발송하지 마세요.]\n" + body
        result.append({"place_id": place.id, "name": place.name, "text": body})
    return result
