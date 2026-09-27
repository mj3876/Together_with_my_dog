"""Exact search for the supported small catalogue. No nearest-place greedy fallback."""
import time
from app.services.schedule_service import make_day
from app.services.course_ranker import rank_key


class SearchLimitError(Exception):
    pass


def find_best(trip, candidates, routes, settings, replacement=None):
    lodgings = candidates["lodging"] if trip.trip_days > 1 else [None]
    restaurants = candidates["restaurant"]
    activities = candidates["activity"]
    best, best_rank = None, None
    states = 0
    deadline = time.monotonic() + 50

    def permitted(place, category, day=1):
        if replacement is None:
            return True
        before = replacement.itinerary
        previous = before.lodging_room if category == "lodging" else getattr(before.days[day - 1], category)
        changed = replacement.slot == category and (category == "lodging" or replacement.day_number == day)
        return place.id != previous.id if changed else place.id == previous.id

    for lodging in lodgings:
        if lodging and not permitted(lodging, "lodging"):
            continue
        memo = {}
        options_by_day = {}
        for day in range(1, trip.trip_days + 1):
            options = []
            for restaurant in restaurants:
                if not permitted(restaurant, 'restaurant', day):
                    continue
                for activity in activities:
                    if not permitted(activity, 'activity', day):
                        continue
                    if time.monotonic() > deadline:
                        raise SearchLimitError('후보 조합 계산 시간 한도에 도달했습니다.')
                    for reverse in (False, True):
                        plan = make_day(day, trip, lodging, restaurant, activity, reverse, routes, settings)
                        if plan:
                            options.append(plan)
            options.sort(key=lambda d: (d.total_drive_seconds, d.max_leg_seconds, tuple(s.place.id for s in d.stops)))
            options_by_day[day] = options
        if any(not options for options in options_by_day.values()):
            continue
        # An admissible lower bound: allow venue/program reuse only for the bound.
        # Actual plans still enforce uniqueness. This never excludes a better course.
        remaining_min = {trip.trip_days + 1: 0}
        for day in range(trip.trip_days, 0, -1):
            remaining_min[day] = remaining_min[day + 1] + options_by_day[day][0].total_drive_seconds

        def visit(day, used_r, used_a, plans, cost):
            nonlocal states, best, best_rank
            if best_rank is not None and cost + remaining_min[day] > best_rank[0]:
                return
            states += 1
            if states > settings.max_search_states or time.monotonic() > deadline:
                raise SearchLimitError("후보 조합이 계산 한도를 초과했습니다. 운영자가 데이터 범위·계산 한도를 조정해야 합니다.")
            if day > trip.trip_days:
                key = rank_key(lodging, plans)
                if best_rank is None or key < best_rank:
                    best_rank, best = key, (lodging, list(plans))
                return
            state = (day, frozenset(used_r), frozenset(used_a))
            # Only strictly cheaper prefixes dominate. Equal-cost prefixes can differ
            # in the longest leg or stable tie key, so they must remain searchable.
            if state in memo and memo[state] < cost:
                return
            memo[state] = min(cost, memo.get(state, cost))
            for plan in options_by_day[day]:
                if best_rank is not None and cost + plan.total_drive_seconds + remaining_min[day + 1] > best_rank[0]:
                    break
                if plan.restaurant.venue_id in used_r or plan.activity.id in used_a:
                    continue
                visit(day + 1, used_r | {plan.restaurant.venue_id}, used_a | {plan.activity.id},
                      [*plans, plan], cost + plan.total_drive_seconds)

        visit(1, set(), set(), [], 0)
    return best
