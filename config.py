import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    FILE_STORAGE_PATH = Path(
        os.getenv("FILE_STORAGE_PATH", str(BASE_DIR / "storage" / "files"))
    )
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 50 * 1024 * 1024))

    SKLM_BASE_URL = os.getenv("SKLM_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    SKLM_USERNAME = os.getenv("SKLM_USERNAME")
    SKLM_PASSWORD = os.getenv("SKLM_PASSWORD")
    SKLM_KEK_ID = os.getenv("SKLM_KEK_ID")
    SKLM_VERIFY_TLS = _env_bool("SKLM_VERIFY_TLS", False)
    SKLM_CONNECT_TIMEOUT = float(os.getenv("SKLM_CONNECT_TIMEOUT", "3"))
    SKLM_READ_TIMEOUT = float(os.getenv("SKLM_READ_TIMEOUT", "10"))

    DEBUG = _env_bool("DEBUG", True)
