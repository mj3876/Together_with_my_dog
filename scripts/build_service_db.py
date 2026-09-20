import argparse
import json
from pathlib import Path
from app.core.config import Settings
from app.db.session import make_engine
from app.schemas.place import Place
from app.repositories.place_repository import upsert_places


def import_catalog(paths, database_path):
    places = []
    for path in paths:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        if not isinstance(data, list):
            raise ValueError("각 JSON 파일은 장소 객체 배열이어야 합니다.")
        places.extend(Place.model_validate(row) for row in data)
    if len({p.id for p in places}) != len(places):
        raise ValueError("입력 자료에 중복 id가 있습니다. 원본을 정리한 뒤 적재하세요.")
    for p in places:
        if p.is_demo:
            raise ValueError("데모 자료는 실제 DB에 적재할 수 없습니다.")
        if not p.address.startswith(("대전광역시 ", "대전 ")):
            raise ValueError(f"{p.id}: 대전 주소가 아닙니다.")
        if not 36.1 < p.latitude < 36.55 or not 127.2 < p.longitude < 127.65:
            raise ValueError(f"{p.id}: 대전 권역 밖 좌표입니다. 정확한 행정구역은 공식 주소로 확인하세요.")
        policy = p.policy
        if p.active and (not policy.verified or not policy.pet_allowed
                         or (policy.max_dogs is None and not policy.dogs_unlimited)
                         or (policy.max_weight_kg is None and not policy.weight_unlimited)):
            raise ValueError(f"{p.id}: 활성 장소의 동반·마릿수·체중 규정 근거를 확인하세요.")
    engine = make_engine(database_path)
    try:
        upsert_places(engine, places)
    finally:
        engine.dispose()
    return len(places)


def main():
    parser = argparse.ArgumentParser(description="검토한 JSON을 검증 후 SQLite에 원자적으로 적재합니다. 같은 id는 갱신합니다.")
    parser.add_argument("inputs", type=Path, nargs="+")
    parser.add_argument("--database", default=None)
    args = parser.parse_args()
    try:
        count = import_catalog(args.inputs, args.database or Settings.from_env().database_path)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"적재하지 않았습니다: {exc}\n")
    print(f"장소 {count}개 적재 완료. 데이터 자체의 운영·정책 근거는 운영자가 관리합니다.")


if __name__ == "__main__":
    main()
