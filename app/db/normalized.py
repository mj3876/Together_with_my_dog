"""Versioned extensions to the reviewed normalized schema."""
from pathlib import Path
import sqlite3
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[2]
EXTENSION = """
CREATE TABLE IF NOT EXISTS schema_versions(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS offering_details (
    offering_id TEXT PRIMARY KEY NOT NULL REFERENCES offerings,
    description TEXT NOT NULL DEFAULT '',
    product_name TEXT NOT NULL DEFAULT '',
    schedule_note TEXT NOT NULL DEFAULT '',
    price_note TEXT NOT NULL DEFAULT '',
    source_url TEXT,
    source_quote TEXT NOT NULL DEFAULT '',
    opens_minute INTEGER,
    closes_minute INTEGER,
    CHECK ((opens_minute IS NULL AND closes_minute IS NULL) OR
      (opens_minute IS NOT NULL AND closes_minute IS NOT NULL AND
       opens_minute>=0 AND closes_minute<=1439 AND opens_minute<closes_minute))
);
INSERT OR IGNORE INTO schema_versions VALUES (1, datetime('now'));
CREATE TABLE IF NOT EXISTS reference_planning (
    offering_id TEXT NOT NULL PRIMARY KEY REFERENCES offerings,
    enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
    activity_minutes INTEGER NOT NULL DEFAULT 60 CHECK(activity_minutes>0),
    configured_at TEXT NOT NULL,
    note TEXT NOT NULL
);
INSERT OR IGNORE INTO schema_versions VALUES (2, datetime('now'));
"""


def initialize(connection):
    connection.execute("PRAGMA foreign_keys=ON")
    names = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "places" in names:
        raise ValueError("기존 app.db에 정규화 초기화를 적용할 수 없습니다.")
    if not names:
        connection.executescript((ROOT / "docs/database_schema.sql").read_text(encoding="utf-8"))
    elif not {"venues", "offerings", "pet_policy_versions"}.issubset(names):
        raise ValueError("알 수 없는 DB 구조입니다.")
    connection.executescript(EXTENSION)


@contextmanager
def open_readonly(path):
    connection = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        yield connection
    finally:
        connection.close()
