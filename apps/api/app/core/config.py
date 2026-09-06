from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "repo2web"
    APP_ENV: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/repo2web"

    REDIS_URL: str = "redis://localhost:6379/0"

    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    GITHUB_TOKEN: Optional[str] = None

    DOCKER_SOCKET: str = "unix:///var/run/docker.sock"

    BUILD_TIMEOUT: int = 300
    RUNTIME_TTL_HOURS: int = 24
    MAX_CONCURRENT_BUILDS: int = 5

    LOG_LEVEL: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
