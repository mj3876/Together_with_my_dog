from datetime import date


def eligible(place, trip, demo=False):
    p = place.policy
    reference = place.planning_mode == "reference" and not demo
    if not place.active or place.is_demo != demo or not place.address.startswith(("대전광역시 ", "대전 ")):
        return False
    if not p.pet_allowed:
        return False
    if (not reference and (not p.verified or p.checked_at is None)) or (p.checked_at and p.checked_at > date.today()):
        return False
    if not p.dogs_unlimited:
        if p.max_dogs is None and not reference:
            return False
        if p.max_dogs is not None and trip.dog_count > p.max_dogs:
            return False
    if not p.weight_unlimited:
        if p.max_weight_kg is None and not reference:
            return False
        if p.max_weight_kg is not None and any(w > p.max_weight_kg or (p.weight_operator == "lt" and w == p.max_weight_kg) for w in trip.dog_weights_kg):
            return False
    if place.category == "restaurant" and not place.serves_meals and not reference:
        return False
    if place.category == "lodging" and not place.product_name:
        return False
    if place.category == "activity" and (not place.product_name or (not place.recurring and not reference)):
        return False
    return True
