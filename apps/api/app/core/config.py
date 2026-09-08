from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "repo2web"
    APP_ENV: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = ""  # MUST be set via environment variable in production

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

    def validate_for_production(self) -> list[str]:
        """Validate settings for production deployment."""
        violations = []
        if self.is_production:
            if not self.SECRET_KEY or self.SECRET_KEY == "":
                violations.append("SECRET_KEY must be set in production")
            if "localhost" in self.DATABASE_URL:
                violations.append("DATABASE_URL should not use localhost in production")
        return violations


@lru_cache
def get_settings() -> Settings:
    return Settings()
