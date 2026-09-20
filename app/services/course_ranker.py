def stable_key(lodging, days):
    return (lodging.id if lodging else "", tuple(tuple(s.place.id for s in d.stops) for d in days))


def rank_key(lodging, days):
    return (sum(d.total_drive_seconds for d in days), max(d.max_leg_seconds for d in days), stable_key(lodging, days))
