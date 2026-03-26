from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BACKEND_DIR / ".env"
SQLITE_PREFIX = "sqlite+aiosqlite:///"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    BASE_DIR: Path = BACKEND_DIR
    DATA_DIR: Path = BASE_DIR / "data"

    OPENAI_API_KEY: str | None = None
    DATABASE_URL: str = f"sqlite+aiosqlite:///{DATA_DIR}/codechat.db"
    CHROMA_PATH: str = str(DATA_DIR / "chroma_db")


settings = Settings()


def _resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (BACKEND_DIR / path).resolve()


def _normalize_sqlite_database_url(database_url: str) -> str:
    if not database_url.startswith(SQLITE_PREFIX):
        return database_url
    raw_path = database_url[len(SQLITE_PREFIX) :]
    normalized = _resolve_path(raw_path)
    return f"{SQLITE_PREFIX}{normalized.as_posix()}"


settings.DATABASE_URL = _normalize_sqlite_database_url(settings.DATABASE_URL)
settings.CHROMA_PATH = str(_resolve_path(settings.CHROMA_PATH))

try:
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
except Exception as exc:
    print(f"CRITICAL WARNING: Could not create data directory at {settings.DATA_DIR}: {exc}")
