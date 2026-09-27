from collections import Counter
from app.repositories.place_repository import all_places


def catalog_status(engine):
    if getattr(engine, "dog_backend", "legacy") == "normalized":
        from app.repositories.normalized_place_repository import catalog
        _, rows = catalog(engine)
    else:
        rows = [dict(category=p.category, active=p.active and p.policy.verified) for p in all_places(engine)]
    return {"total": len(rows), "active": sum(r["active"] for r in rows),
            "by_category": dict(Counter(r["category"] for r in rows)),
            "active_by_category": dict(Counter(r["category"] for r in rows if r["active"]))}
