from app.schemas.itinerary import DayPlan, Stop
from app.schemas.trip import Point


def plain_point(value):
    return Point(**value.model_dump(include={"name", "latitude", "longitude"}))


def make_day(day, trip, lodging, restaurant, activity, reverse, routes, settings):
    if activity.duration_minutes is None:
        return None
    origin = trip.start_point if day == 1 else lodging
    destination = trip.end_point if day == trip.trip_days else lodging
    start = settings.day_start_minutes
    if lodging and day == trip.trip_days:
        start = min(start, lodging.checkout_minute)
    cursor = float(start)
    current = origin
    legs, stops = [], []
    for place in ([activity, restaurant] if reverse else [restaurant, activity]):
        leg = routes.get(current, place)
        if leg is None:
            return None
        legs.append(leg)
        arrival = cursor + leg.duration_seconds / 60 + settings.buffer_minutes
        begin = max(arrival, place.opens_minute or 0)
        duration = settings.meal_minutes if place.category == "restaurant" else place.duration_minutes
        end = begin + duration
        if place.closes_minute is not None and end > place.closes_minute:
            return None
        stops.append(Stop(place=place, arrival_minute=arrival, start_minute=begin,
                          end_minute=end, wait_minutes=begin - arrival))
        cursor, current = end, place
    leg = routes.get(current, destination)
    if leg is None:
        return None
    legs.append(leg)
    cursor += leg.duration_seconds / 60 + settings.buffer_minutes
    lodging_wait = 0
    if lodging and day == 1:
        lodging_wait = max(0, lodging.checkin_minute - cursor)
        cursor += lodging_wait
    if cursor - start > settings.day_limit_minutes:
        return None
    return DayPlan(day_number=day, start_point=plain_point(origin), end_point=plain_point(destination),
                   restaurant=restaurant, activity=activity, stops=stops, route_legs=legs,
                   start_minute=start, end_minute=cursor, estimated_duration_seconds=round((cursor - start) * 60),
                   total_drive_seconds=sum(x.duration_seconds for x in legs),
                   max_leg_seconds=max(x.duration_seconds for x in legs), lodging_wait_minutes=lodging_wait)
