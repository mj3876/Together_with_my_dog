from sqlalchemy import JSON, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PlaceRecord(Base):
    __tablename__ = "places"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    category: Mapped[str] = mapped_column(String(20), index=True)
    document: Mapped[dict] = mapped_column(JSON)
