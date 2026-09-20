from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from app.models.place import Base


def make_engine(path: str, memory=False):
    if memory:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    else:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine("sqlite:///" + str(Path(path).resolve()), connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return engine
