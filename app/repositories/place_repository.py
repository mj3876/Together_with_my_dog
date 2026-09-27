from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.place import PlaceRecord
from app.schemas.place import Place


def all_places(engine) -> list[Place]:
    if getattr(engine, "dog_backend", "legacy") == "normalized":
        from app.repositories.normalized_place_repository import catalog
        return catalog(engine)[0]
    with Session(engine) as session:
        return [Place.model_validate(r.document) for r in session.scalars(select(PlaceRecord).order_by(PlaceRecord.id))]


def get_place(engine, place_id):
    if getattr(engine, "dog_backend", "legacy") == "normalized":
        return next((p for p in all_places(engine) if p.id == place_id), None)
    with Session(engine) as session:
        row = session.get(PlaceRecord, place_id)
        return Place.model_validate(row.document) if row else None


def upsert_places(engine, places: list[Place]):
    if getattr(engine, "dog_backend", "legacy") == "normalized":
        raise ValueError("정규화 DB는 migrate_service_db로 갱신하세요.")
    # Caller validates the complete input before this atomic transaction.
    with Session(engine) as session, session.begin():
        for place in places:
            session.merge(PlaceRecord(id=place.id, category=place.category, document=place.model_dump(mode="json")))
