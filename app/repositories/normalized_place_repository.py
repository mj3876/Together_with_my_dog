"""Keep source facts separate from explicitly configured reference planning rules."""
from datetime import date
from sqlalchemy import text
from app.schemas.place import Place


def catalog(engine):
    places, report = [], []
    with engine.connect() as conn:
        rows = conn.execute(text("""
          SELECT o.*, v.name AS venue_name, v.address, v.latitude, v.longitude,
                 v.official_url, p.policy_id, p.review_status AS policy_status,
                 p.checked_at, p.pet_allowed, p.dogs_limit_state, p.max_dogs,
                 p.weight_limit_state, p.max_weight_kg, p.weight_operator,
                 p.effective_from, p.effective_to,
                 d.description, d.product_name, d.schedule_note, d.price_note,
                 d.source_url, d.source_quote, d.opens_minute, d.closes_minute
          FROM offerings o JOIN venues v USING(venue_id)
          LEFT JOIN pet_policy_versions p ON p.offering_id=o.offering_id AND p.is_current=1
          LEFT JOIN offering_details d USING(offering_id)
          ORDER BY o.offering_id
        """)).mappings().all()
        conditions = conn.execute(text("SELECT policy_id, summary, enforcement FROM policy_conditions")).mappings().all()
        issues = conn.execute(text("SELECT offering_id, venue_id, field_name, description FROM review_issues WHERE status='open'")).mappings().all()
        evidence = {r[0] for r in conn.execute(text("SELECT DISTINCT policy_id FROM policy_evidence"))}
        dated = {r[0] for r in conn.execute(text("SELECT offering_id FROM opening_hours UNION SELECT offering_id FROM schedule_exceptions"))}
        has_reference = conn.execute(text("SELECT 1 FROM sqlite_master WHERE name='reference_planning' AND type='table'")).first()
        overrides = {r['offering_id']:r for r in conn.execute(text('SELECT * FROM reference_planning WHERE enabled=1')).mappings()} if has_reference else {}
    for r in rows:
        reference = r['offering_id'] in overrides
        reasons = []
        if not r["enabled"]: reasons.append("미활성")
        if r["policy_status"] != "verified": reasons.append("동반 규정 검증 미완료")
        if r["pet_allowed"] != 1: reasons.append("동반 허용 미확인 또는 금지")
        if r["dogs_limit_state"] not in {"limited", "unlimited"}: reasons.append("마릿수 제한 미확인")
        if r["weight_limit_state"] not in {"limited", "unlimited"}: reasons.append("체중 제한 미확인")
        if not r["source_url"] or not r["source_quote"] or r["policy_id"] not in evidence:
            reasons.append("규정 근거 부족")
        try:
            checked = date.fromisoformat(r["checked_at"] or "")
            if checked > date.today(): reasons.append("미래 확인일")
            if r["effective_from"] and date.fromisoformat(r["effective_from"]) > date.today(): reasons.append("시행 전 규정")
            if r["effective_to"] and date.fromisoformat(r["effective_to"]) <= date.today(): reasons.append("종료된 규정")
        except ValueError:
            checked = None
            reasons.append("확인일/시행일 오류")
        coords = r["latitude"] is not None and r["longitude"] is not None
        if not coords: reasons.append("좌표 미확인")
        elif not (36.1 < r["latitude"] < 36.55 and 127.2 < r["longitude"] < 127.65): reasons.append("대전 권역 밖 좌표")
        if not r["address"].startswith(("대전 ", "대전광역시 ")): reasons.append("대전 주소 미확인")
        requirements = [c["summary"] for c in conditions if c["policy_id"] == r["policy_id"]]
        if any(c["enforcement"] != "informational" for c in conditions if c["policy_id"] == r["policy_id"]):
            reasons.append("현재 입력으로 판정하지 못하는 필수 조건")
        reasons.extend(i["description"] for i in issues if i["offering_id"] == r["offering_id"] or (i["offering_id"] is None and i["venue_id"] == r["venue_id"]))
        if r["offering_id"] in dated: reasons.append("날짜/요일별 운영 조건 확인 필요")
        if r["category"] == "restaurant" and not r["serves_meals"]: reasons.append("식사 메뉴 미확인")
        if r["category"] in {"lodging", "activity"} and not r["product_name"]: reasons.append("상품명 미확인")
        if r["category"] == "activity" and (not r["recurring"] or not r["duration_minutes"]): reasons.append("체험 운영 방식/소요시간 미확인")
        notes = []
        duration = r['duration_minutes']
        estimated = False
        if reference:
            # Reference planning is an operator rule, not evidence of venue permission.
            reasons = []
            if r['pet_allowed'] != 1: reasons.append('반려견 동반 허용 미확인 또는 금지')
            if r['policy_status'] in {'conflict', 'rejected'}: reasons.append('동반 규정 충돌 또는 반려')
            if not coords: reasons.append('좌표 미확인')
            elif not (36.1 < r['latitude'] < 36.55 and 127.2 < r['longitude'] < 127.65): reasons.append('대전 권역 밖 좌표')
            if not r['address'].startswith(('대전 ', '대전광역시 ')): reasons.append('대전 주소 미확인')
            if checked and checked > date.today(): reasons.append('미래 확인일')
            for field,comparison,label in [('effective_from',lambda d:d>date.today(),'시행 전 규정'),('effective_to',lambda d:d<=date.today(),'종료된 규정')]:
                if r[field]:
                    try:
                        if comparison(date.fromisoformat(r[field])): reasons.append(label)
                    except ValueError: reasons.append('규정 시행일 오류')
            if not r['source_url'] or r['policy_id'] not in evidence: reasons.append('동반 허용 출처 부족')
            reasons.extend(i['description'] for i in issues if i['field_name'] != 'review' and
                (i['offering_id'] == r['offering_id'] or (i['offering_id'] is None and i['venue_id'] == r['venue_id'])))
            if r['dogs_limit_state'] == 'unknown': notes.append('마릿수 제한 미확인: 추천 계산에서는 마릿수 제한 없이 포함합니다.')
            if r['weight_limit_state'] == 'unknown': notes.append('체중 제한 미확인: 추천 계산에서는 체중 제한 없이 포함합니다.')
            if r['category'] == 'restaurant':
                if not r['serves_meals']: notes.append('동반 음식점 등록 자료로 포함했습니다. 식사 메뉴는 미확인입니다.')
                notes.append('실내·테라스 등 동반 공간은 방문 전 확인이 필요합니다.')
            if r['category'] == 'activity':
                if duration is None:
                    duration = overrides[r['offering_id']]['activity_minutes']
                    estimated = True
                    notes.append(f'체험 소요시간 미확인: 일정에 기본 {duration}분을 배정했습니다.')
                if not r['recurring']: notes.append('운영일·회차 미확인: 방문 날짜의 이용 가능 여부를 확인해 주세요.')
            if requirements: notes.append('참가·입장 조건은 추가 입력 없이 안내합니다. 실제 충족 여부는 방문 전에 확인해 주세요.')
            if r['offering_id'] in dated: notes.append('날짜별 운영시간·예약은 확정되지 않은 참고 일정입니다.')
        if coords:
            try:
                place = Place(
                    id=r["offering_id"], venue_id=r["venue_id"], name=r["venue_name"], category=r["category"],
                    address=r["address"], latitude=r["latitude"], longitude=r["longitude"],
                    active=not reasons, is_demo=False, description=r["description"] or "",
                    product_name=r["product_name"] or "", serves_meals=bool(r["serves_meals"]),
                    recurring=bool(r["recurring"]), duration_minutes=duration,
                    planning_mode='reference' if reference else 'verified', planning_notes=notes, duration_is_estimated=estimated,
                    participation_mode=r["participation_mode"], official_url=r["official_url"],
                    checkin_minute=r["checkin_minute"] if r["checkin_minute"] is not None else 900,
                    checkout_minute=r["checkout_minute"] if r["checkout_minute"] is not None else 660,
                    opens_minute=r["opens_minute"], closes_minute=r["closes_minute"],
                    schedule_note=r["schedule_note"] or "방문일 운영 확인 필요", price_note=r["price_note"] or "",
                    policy=dict(verified=r["policy_status"] == "verified", pet_allowed=r["pet_allowed"] == 1,
                                max_dogs=r["max_dogs"], dogs_unlimited=r["dogs_limit_state"] == "unlimited",
                                max_weight_kg=r["max_weight_kg"], weight_unlimited=r["weight_limit_state"] == "unlimited",
                                weight_operator=r["weight_operator"] or "lte", checked_at=checked,
                                source_url=r["source_url"], source_quote=r["source_quote"] or "", requirements=requirements))
                places.append(place)
            except ValueError:
                reasons.append("앱 장소 스키마 불일치")
        report.append(dict(id=r["offering_id"], name=r["venue_name"], category=r["category"],
                           active=not reasons, planning_mode='reference' if reference else 'verified',
                           notes=notes, reasons=list(dict.fromkeys(reasons))))
    return places, report
