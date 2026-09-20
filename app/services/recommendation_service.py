from app.core.signing import sign
from app.repositories.place_repository import all_places
from app.schemas.itinerary import Itinerary
from app.schemas.recommendation import Recommendation
from app.services.policy_matcher import eligible
from app.services.itinerary_service import find_best, SearchLimitError
from app.services.route_service import RouteService, RouteBudgetError


def recommend(trip, engine, settings, replacement=None, route_service=None):
    candidates = {k: [] for k in ("lodging", "restaurant", "activity")}
    unknown_duration = 0
    for place in all_places(engine):
        if eligible(place, trip, settings.mode == "demo"):
            if place.category == "activity" and place.duration_minutes is None:
                unknown_duration += 1
                continue
            candidates[place.category].append(place)
    reasons = []
    if trip.trip_days > 1 and not candidates["lodging"]:
        reasons.append("반려견 수·체중에 맞는 동반 객실 데이터가 없습니다.")
    nr = len({p.venue_id for p in candidates["restaurant"]})
    na = len(candidates["activity"])
    if nr < trip.trip_days:
        reasons.append(f"{trip.trip_days}일에 필요한 식당은 {trip.trip_days}곳이며, 조건에 맞는 등록 식당은 {nr}곳입니다.")
    if na < trip.trip_days:
        reasons.append(f"{trip.trip_days}일에 필요한 체험은 {trip.trip_days}개이며, 조건·소요시간을 확인한 프로그램은 {na}개입니다.")
        if unknown_duration:
            reasons.append(f"체험 {unknown_duration}개는 운영 측 소요시간 자료 보완이 필요합니다.")
    if reasons:
        return Recommendation(status="no_match", reasons=reasons)
    if settings.mode == "live" and not settings.mobility_key and route_service is None:
        return Recommendation(status="route_unavailable", reasons=["자동차 이동시간 연결이 준비되지 않았습니다. 운영자가 경로 API 설정을 확인해야 합니다."])
    routes = route_service or RouteService(settings)
    try:
        result = find_best(trip, candidates, routes, settings, replacement)
        if result is None:
            return Recommendation(status="route_unavailable" if routes.missing else "no_match",
                                  reasons=["이동정보와 일차별 참고 일정 기준을 충족하는 완성 코스가 없습니다."])
        lodging, days = result
        places = ([lodging] if lodging else []) + [s.place for d in days for s in d.stops]
        total = sum(d.total_drive_seconds for d in days)
        requirements = ["날짜를 지정하지 않은 계획입니다. 실제 영업·체험 회차·예약 재고는 방문 전에 확인해 주세요.",
                        "동반 인원을 입력받지 않았습니다. 객실 정원과 프로그램 참가 인원을 확인해 주세요."]
        for place in places:
            requirements.extend(f"{place.name}: {r}" for r in [*place.policy.requirements, place.schedule_note])
        basis = ["자동차 기준 · 조회 시점의 참고 이동시간", "하루 식사 1회·체험 1개, 숙소는 거점 연박",
                 "일차별 10:00 시작 예시 · 식사 60분 · 구간당 준비 10분 · 하루 8시간 이내",
                 "마지막 날은 숙소 체크아웃 시각에 맞춰 출발 예시를 앞당길 수 있습니다.",
                 "등록 후보·확보된 경로·거점 연박 구조 안에서 전체 주행시간 최소"]
        if routes.missing:
            basis.append("일부 경로를 조회하지 못해 이동정보가 확보된 조합만 비교했습니다.")
        if settings.mode == "demo":
            basis.insert(0, "데모: 모든 업체·규정·이동시간은 가상입니다. 실제 방문용으로 사용할 수 없습니다.")
        itinerary = Itinerary(
            request=trip, nights=trip.trip_days - 1, lodging_room=lodging, days=days,
            total_drive_seconds=total, max_leg_seconds=max(d.max_leg_seconds for d in days),
            planning_basis=basis, reasons=[f"반려견 {trip.dog_count}마리의 각 체중 조건에 맞는 장소",
                                         f"{trip.trip_days}일 전체 예상 주행 {round(total / 60)}분",
                                         "비교 가능한 조합 중 전체 주행시간이 가장 짧은 코스"],
            visit_requirements=list(dict.fromkeys(requirements)), is_demo=settings.mode == "demo")
        itinerary.integrity_token = sign(itinerary.model_dump(mode="json", exclude={"integrity_token"}), settings.signing_key, "itinerary")
        return Recommendation(status="recommended", itinerary=itinerary, reasons=itinerary.reasons)
    except RouteBudgetError as exc:
        return Recommendation(status="route_unavailable", reasons=[str(exc)])
    except SearchLimitError as exc:
        # Never silently return an unproven partial optimum.
        return Recommendation(status="planning_limit", reasons=[str(exc)])
    finally:
        if route_service is None:
            routes.close()
