from pathlib import Path
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.pool import StaticPool
from app.models.place import Base


def make_engine(path: str, memory=False, backend="legacy"):
    if backend not in {"legacy", "normalized"}:
        raise ValueError("Unknown database backend")
    if memory:
        backend = "legacy"
    if backend == "normalized" and not Path(path).is_file():
        raise ValueError("정규화 DB가 없습니다. migrate_service_db를 먼저 실행하세요.")
    if memory:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    else:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine("sqlite:///" + str(Path(path).resolve()), connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    tables = set(inspect(engine).get_table_names())
    if backend == "normalized":
        required = {"venues", "offerings", "pet_policy_versions", "offering_details", "policy_evidence", "review_issues"}
        if not required.issubset(tables):
            engine.dispose()
            raise ValueError("정규화 DB 스키마가 준비되지 않았습니다.")
    else:
        if "offerings" in tables:
            engine.dispose()
            raise ValueError("정규화 DB에 legacy 저장소로 연결할 수 없습니다.")
        Base.metadata.create_all(engine)
    engine.dog_backend = backend
    return engine
