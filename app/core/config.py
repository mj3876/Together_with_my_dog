from dataclasses import dataclass, field
from pathlib import Path
import os
import secrets

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    mode: str = "live"
    database_path: str = str(ROOT / "data/app.db")
    kakao_key: str = field(default="", repr=False)
    mobility_key: str = field(default="", repr=False)
    signing_key: str = field(default_factory=lambda: secrets.token_hex(32), repr=False)
    max_route_requests: int = 500
    max_search_states: int = 250000
    day_start_minutes: int = 600
    day_limit_minutes: int = 480
    meal_minutes: int = 60
    buffer_minutes: int = 10

    @classmethod
    def from_env(cls):
        load_dotenv(ROOT / ".env")
        mode = os.getenv("APP_MODE", "live")
        if mode not in {"live", "demo"}:
            raise ValueError("APP_MODE must be live or demo")
        key = os.getenv("LOCATION_SIGNING_KEY", "")
        if not key:
            path = ROOT / ".secrets/location_signing.key"
            path.parent.mkdir(exist_ok=True)
            try:
                with path.open("x", encoding="utf-8") as handle:
                    handle.write(secrets.token_hex(32))
            except FileExistsError:
                pass
            key = path.read_text(encoding="utf-8").strip()
        path = Path(os.getenv("DATABASE_PATH", "data/app.db"))
        return cls(
            mode=mode, database_path=str(path if path.is_absolute() else ROOT / path),
            kakao_key=os.getenv("KAKAO_REST_API_KEY", ""),
            mobility_key=os.getenv("KAKAO_MOBILITY_API_KEY", ""), signing_key=key,
            max_route_requests=max(1, int(os.getenv("MAX_ROUTE_REQUESTS", "500"))),
            max_search_states=max(1, int(os.getenv("MAX_SEARCH_STATES", "250000"))),
        )
