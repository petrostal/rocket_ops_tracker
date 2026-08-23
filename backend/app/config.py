from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=True,
        enable_decoding=False,
    )

    app_env: Literal["development", "test", "production"] = Field("development", alias="APP_ENV")
    app_secret: str = Field("development-only-change-me", alias="APP_SECRET")
    database_url: str = Field("sqlite+pysqlite:///./opstracker.db", alias="DATABASE_URL")
    public_url: str = Field("http://localhost:8080", alias="PUBLIC_URL")
    rocketchat_url: str = Field("http://localhost:3000", alias="ROCKETCHAT_URL")
    rocketchat_client_id: str = Field("", alias="ROCKETCHAT_CLIENT_ID")
    rocketchat_client_secret: str = Field("", alias="ROCKETCHAT_CLIENT_SECRET")
    rocketchat_bot_user_id: str = Field("", alias="ROCKETCHAT_BOT_USER_ID")
    rocketchat_bot_token: str = Field("", alias="ROCKETCHAT_BOT_TOKEN")
    rocketchat_app_secret: str = Field("development-app-secret", alias="ROCKETCHAT_APP_SECRET")
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:8080"],
        alias="ALLOWED_ORIGINS",
    )
    allowed_frame_origin: str = Field("'none'", alias="ALLOWED_FRAME_ORIGIN")
    task_admin_usernames: set[str] = Field(default_factory=set, alias="TASK_ADMIN_USERNAMES")
    session_ttl_minutes: int = Field(480, alias="SESSION_TTL_MINUTES", ge=5, le=10080)
    integration_max_age_seconds: int = Field(300, alias="INTEGRATION_MAX_AGE_SECONDS", ge=30, le=900)
    launch_code_ttl_seconds: int = Field(60, alias="LAUNCH_CODE_TTL_SECONDS", ge=15, le=300)
    notify_task_created: bool = Field(True, alias="NOTIFY_TASK_CREATED")
    notify_task_assigned: bool = Field(True, alias="NOTIFY_TASK_ASSIGNED")
    notify_task_started: bool = Field(False, alias="NOTIFY_TASK_STARTED")
    notify_task_completed: bool = Field(True, alias="NOTIFY_TASK_COMPLETED")
    notify_task_overdue: bool = Field(True, alias="NOTIFY_TASK_OVERDUE")
    notify_creator_updates: bool = Field(True, alias="NOTIFY_CREATOR_UPDATES")
    attachments_dir: str = Field("/data/attachments", alias="ATTACHMENTS_DIR")
    attachment_max_bytes: int = Field(
        25 * 1024 * 1024, alias="ATTACHMENT_MAX_BYTES", ge=1024, le=1024 * 1024 * 1024
    )
    attachment_max_per_task: int = Field(50, alias="ATTACHMENT_MAX_PER_TASK", ge=1, le=10000)
    attachment_total_max_bytes_per_task: int = Field(
        250 * 1024 * 1024,
        alias="ATTACHMENT_TOTAL_MAX_BYTES_PER_TASK",
        ge=1024,
        le=100 * 1024 * 1024 * 1024,
    )
    attachment_total_max_bytes_per_user: int = Field(
        1024 * 1024 * 1024,
        alias="ATTACHMENT_TOTAL_MAX_BYTES_PER_USER",
        ge=1024,
        le=1024 * 1024 * 1024 * 1024,
    )
    comment_max_per_task: int = Field(1000, alias="COMMENT_MAX_PER_TASK", ge=1, le=100000)
    overdue_check_interval_seconds: int = Field(
        300, alias="OVERDUE_CHECK_INTERVAL_SECONDS", ge=30, le=86400
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]
        return value

    @field_validator("task_admin_usernames", mode="before")
    @classmethod
    def parse_admins(cls, value: object) -> object:
        if isinstance(value, str):
            return {item.strip().lower() for item in value.split(",") if item.strip()}
        return value

    def validate_production(self) -> None:
        if self.app_env != "production":
            return

        if _is_public_placeholder(self.app_secret) or len(self.app_secret) < 32:
            raise RuntimeError("APP_SECRET must be a random value of at least 32 characters")
        if _is_public_placeholder(self.rocketchat_app_secret) or len(self.rocketchat_app_secret) < 32:
            raise RuntimeError("ROCKETCHAT_APP_SECRET must be a random value of at least 32 characters")
        if not self.rocketchat_client_id or not self.rocketchat_client_secret:
            raise RuntimeError("Rocket.Chat OAuth client credentials are required in production")
        if _is_public_placeholder(self.rocketchat_client_secret):
            raise RuntimeError("ROCKETCHAT_CLIENT_SECRET must be deployment-specific")
        if self.rocketchat_bot_token and _is_public_placeholder(self.rocketchat_bot_token):
            raise RuntimeError("ROCKETCHAT_BOT_TOKEN must be deployment-specific")
        _require_https_origin("PUBLIC_URL", self.public_url)
        _require_https_origin("ROCKETCHAT_URL", self.rocketchat_url)
        _require_https_origin("ALLOWED_FRAME_ORIGIN", self.allowed_frame_origin)
        if not self.allowed_origins:
            raise RuntimeError("ALLOWED_ORIGINS must not be empty in production")
        for origin in self.allowed_origins:
            _require_https_origin("ALLOWED_ORIGINS", origin)

        database = make_url(self.database_url)
        if database.drivername.startswith("sqlite"):
            raise RuntimeError("DATABASE_URL must use a production database")
        if not database.username or not database.password or _is_public_placeholder(database.password):
            raise RuntimeError("DATABASE_URL must contain deployment-specific credentials")


def _is_public_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    markers = (
        "change-me",
        "changeme",
        "development-",
        "example",
        "generate-",
        "placeholder",
        "replace-",
        "test-",
        "your-",
    )
    return not normalized or any(marker in normalized for marker in markers)


def _require_https_origin(name: str, value: str) -> None:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError(f"{name} must be an HTTPS origin without credentials, path, query, or fragment")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production()
    return settings
