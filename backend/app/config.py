from datetime import timedelta, timezone
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
IST = timezone(timedelta(hours=5, minutes=30), "IST")  # India has no DST, so a fixed offset is exact


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    data_dir: Path = BACKEND_DIR / "data"
    seed_dir: Path = BACKEND_DIR / "seed"

    # LLM routing: a cheap tier for bulk extraction, a strong tier only where reasoning needs it
    anthropic_api_key: str | None = None
    model_cheap: str = "claude-haiku-5-5"
    model_strong: str = "claude-sonnet-5-5"
    llm_enabled: bool = True

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Politeness towards public sources
    http_min_interval_s: float = 0.6
    screener_cache_hours: float = 12.0

    # Market close + buffer before today's EOD bar is treated as final
    eod_final_after_ist: str = "16:00"

    # Periodic refresh on hosts that stay awake; 0 disables it (refresh is then on demand)
    auto_refresh_minutes: int = 0

    @property
    def db_path(self) -> Path:
        return self.data_dir / "finn.sqlite3"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def docs_dir(self) -> Path:
        return self.data_dir / "documents"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"


settings = Settings()
for d in (settings.data_dir, settings.cache_dir, settings.docs_dir):
    d.mkdir(parents=True, exist_ok=True)
