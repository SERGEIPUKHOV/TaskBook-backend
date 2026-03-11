from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_VERSION: str = "6.1.1"
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = "change_me_in_production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    RESET_TOKEN_EXPIRE_MINUTES: int = 60
    DATABASE_URL: str = "sqlite+aiosqlite:///./taskbook.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    AUTO_CREATE_TABLES: bool = False
    RATE_LIMIT_ENABLED: bool = True
    SEED_DEMO_USER: bool = True
    SEED_ADMIN_USER: bool = True
    LOG_LEVEL: str = "INFO"
    DASHBOARD_CACHE_TTL: int = 60
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 3600
    SENTRY_DSN: str | None = None
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1
    ACCESS_COOKIE_NAME: str = "taskbook_access"
    REFRESH_COOKIE_NAME: str = "taskbook_refresh"
    SESSION_COOKIE_NAME: str = "taskbook_session"
    AUTH_COOKIE_DOMAIN: str | None = None
    AUTH_COOKIE_SAMESITE: str = "lax"
    AUTH_COOKIE_SECURE: bool = False
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:3001,http://localhost:3002,http://localhost:3003",
    )
    DEMO_USER_EMAIL: str = "demo@taskbook.app"
    DEMO_USER_PASSWORD: str = "taskbook123"
    ADMIN_USER_EMAIL: str = "admin@taskbook.app"
    ADMIN_USER_PASSWORD: str = "admin123"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [item.strip() for item in self.CORS_ORIGINS.split(",") if item.strip()]

    @property
    def is_development(self) -> bool:
        return self.APP_ENV.lower() == "development"

    @property
    def is_testing(self) -> bool:
        return self.APP_ENV.lower() == "test"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
