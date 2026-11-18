import json
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ENV_FILE_PATH = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    APP_NAME: str = "Camera Intelligence"
    APP_ENV: str = "development"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    # Edge Frame Server & Streaming Bridge settings
    EDGE_FRAME_SERVER_URL: str = "http://127.0.0.1:8001"
    EDGE_FRAME_TIMEOUT_SECONDS: float = 5.0
    MAX_STREAM_VIEWERS_PER_CAMERA: int = 10

    # JWT Authentication settings (configurable via environment variables)
    JWT_SECRET_KEY: str = (
        "dev-insecure-jwt-secret-key-camera-intelligence-change-in-prod-2026"
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret_key(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("JWT_SECRET_KEY cannot be empty.")
        if len(value.strip()) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters long.")
        return value.strip()

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        """Accept either a JSON list or a comma-separated string of origins."""
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                parsed = json.loads(stripped)
                if not isinstance(parsed, list):
                    raise ValueError("CORS_ORIGINS JSON must be a list.")
                return [str(item).strip() for item in parsed if str(item).strip()]
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return [str(item).strip() for item in value if str(item).strip()]

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
