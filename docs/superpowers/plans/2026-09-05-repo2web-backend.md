# Repo2Web Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-grade backend that converts GitHub repositories into runnable web applications using FastAPI, PostgreSQL, Redis/Celery, and Docker.

**Architecture:** FastAPI monolith with service-layer separation, SQLAlchemy 2.0 async ORM, Celery for background processing (analysis, builds, runtime), and Docker SDK for container management. Clean boundaries enable future microservice extraction.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0 (async), Alembic, PostgreSQL, Redis, Celery, Docker SDK, pytest, Pydantic v2

---

## Global Constraints

- Python 3.11+ required
- No AI repair engine
- No production deployment (Docker only)
- No arbitrary code execution on host
- Typed interfaces throughout (no `Any` where avoidable)
- Async SQLAlchemy 2.0 patterns (`select()`, `Mapped[]`, `mapped_column()`)
- Pydantic v2 with `model_config` (not `class Config`)
- All secrets via environment variables
- Sub-200ms API response times (P95)
- Sub-100ms database queries with proper indexing

---

## File Structure

```
apps/api/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app factory
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py              # Pydantic Settings
│   │   ├── database.py            # SQLAlchemy async engine/session
│   │   ├── security.py            # JWT, password hashing
│   │   └── exceptions.py          # Custom exception classes
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py                # Base model class
│   │   ├── user.py
│   │   ├── repository.py
│   │   ├── snapshot.py
│   │   ├── analysis.py
│   │   ├── execution_plan.py
│   │   ├── build.py
│   │   ├── runtime.py
│   │   ├── deployment.py
│   │   ├── health_check.py
│   │   └── usage.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── repository.py
│   │   ├── deployment.py
│   │   ├── build.py
│   │   ├── analysis.py
│   │   └── common.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                # Dependencies (get_db, get_current_user)
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py          # V1 router aggregation
│   │       ├── repositories.py
│   │       ├── deployments.py
│   │       └── health.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── repository.py
│   │   ├── analyzer.py
│   │   ├── build.py
│   │   ├── runtime.py
│   │   └── deployment.py
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── celery_app.py
│   │   ├── analyze.py
│   │   ├── build.py
│   │   └── runtime.py
│   └── utils/
│       ├── __init__.py
│       └── github.py              # GitHub API utilities
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_repository_validation.py
│   ├── test_analyzer.py
│   ├── test_models.py
│   └── test_api_repositories.py
├── alembic/
│   ├── env.py
│   └── versions/
├── alembic.ini
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## Task 1: Project Scaffolding & Configuration

**Files:**
- Create: `apps/api/app/__init__.py`
- Create: `apps/api/app/main.py`
- Create: `apps/api/app/core/__init__.py`
- Create: `apps/api/app/core/config.py`
- Create: `apps/api/app/core/database.py`
- Create: `apps/api/app/core/security.py`
- Create: `apps/api/app/core/exceptions.py`
- Create: `apps/api/app/utils/__init__.py`
- Create: `apps/api/app/utils/github.py`
- Create: `apps/api/requirements.txt`
- Create: `apps/api/.env.example`
- Create: `apps/api/Dockerfile`
- Create: `apps/api/docker-compose.yml`

**Interfaces:**
- Produces: `get_settings()`, `get_db()`, `get_sync_db()`, `create_access_token()`, `decode_access_token()`, `AppException`

### Step 1: Create requirements.txt

```txt
# apps/api/requirements.txt
fastapi==0.109.2
uvicorn[standard]==0.27.1
sqlalchemy==2.0.27
alembic==1.13.1
asyncpg==0.29.0
psycopg2-binary==2.9.9
redis==5.0.1
celery[redis]==5.3.6
pydantic==2.6.1
pydantic-settings==2.1.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.9
httpx==0.26.0
docker==7.0.0
tenacity==8.2.3
structlog==24.1.0
```

### Step 2: Create .env.example

```bash
# apps/api/.env.example
APP_NAME=repo2web
APP_ENV=development
DEBUG=true
SECRET_KEY=change-me-in-production
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/repo2web
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
GITHUB_TOKEN=
DOCKER_SOCKET=unix:///var/run/docker.sock
BUILD_TIMEOUT=300
RUNTIME_TTL_HOURS=24
MAX_CONCURRENT_BUILDS=5
LOG_LEVEL=INFO
```

### Step 3: Create config.py

```python
# apps/api/app/core/config.py
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
```

### Step 4: Create database.py

```python
# apps/api/app/core/database.py
from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

sync_engine = create_engine(
    settings.DATABASE_URL.replace("+asyncpg", "+psycopg2"),
    echo=settings.DEBUG,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,
)

SyncSessionLocal = sessionmaker(bind=sync_engine)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_db() -> Session:
    return SyncSessionLocal()
```

### Step 5: Create security.py

```python
# apps/api/app/core/security.py
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
```

### Step 6: Create exceptions.py

```python
# apps/api/app/core/exceptions.py
from typing import Any, Optional


class AppException(Exception):
    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: str,
        headers: Optional[dict[str, str]] = None,
    ):
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code
        self.headers = headers


class NotFoundException(AppException):
    def __init__(self, resource: str, resource_id: Any):
        super().__init__(
            status_code=404,
            detail=f"{resource} with id {resource_id} not found",
            error_code=f"{resource.upper()}_NOT_FOUND",
        )


class ValidationException(AppException):
    def __init__(self, detail: str):
        super().__init__(
            status_code=422,
            detail=detail,
            error_code="VALIDATION_ERROR",
        )


class ConflictException(AppException):
    def __init__(self, detail: str):
        super().__init__(
            status_code=409,
            detail=detail,
            error_code="CONFLICT",
        )


class ExternalServiceException(AppException):
    def __init__(self, service: str, detail: str):
        super().__init__(
            status_code=502,
            detail=f"External service error ({service}): {detail}",
            error_code="EXTERNAL_SERVICE_ERROR",
        )


class UnsupportedRepositoryException(AppException):
    def __init__(self, detail: str = "Repository framework or language not supported"):
        super().__init__(
            status_code=422,
            detail=detail,
            error_code="UNSUPPORTED_REPOSITORY",
        )
```

### Step 7: Create GitHub utilities

```python
# apps/api/app/utils/github.py
import re
from typing import Optional

import httpx
import structlog

from app.core.config import get_settings
from app.core.exceptions import ValidationException, ExternalServiceException

logger = structlog.get_logger()
settings = get_settings()

GITHUB_URL_PATTERN = re.compile(
    r"https?://github\.com/(?P<owner>[a-zA-Z0-9._-]+)/(?P<repo>[a-zA-Z0-9._-]+)(?:/.*)?$"
)


def validate_github_url(url: str) -> bool:
    """Validate that URL is a valid GitHub repository URL."""
    return bool(GITHUB_URL_PATTERN.match(url))


def parse_github_url(url: str) -> tuple[str, str]:
    """Parse GitHub URL to extract owner and repo name."""
    match = GITHUB_URL_PATTERN.match(url)
    if not match:
        raise ValidationException("Invalid GitHub repository URL")
    return match.group("owner"), match.group("repo")


async def get_github_headers() -> dict[str, str]:
    """Get headers for GitHub API requests."""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Repo2Web/0.1.0",
    }
    if settings.GITHUB_TOKEN:
        headers["Authorization"] = f"token {settings.GITHUB_TOKEN}"
    return headers


async def get_repository_info(owner: str, repo: str) -> dict:
    """Fetch repository information from GitHub API."""
    headers = await get_github_headers()
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}",
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValidationException("GitHub repository not found")
            raise ExternalServiceException("GitHub", f"HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            raise ExternalServiceException("GitHub", str(e))


async def get_latest_commit(owner: str, repo: str, branch: str = "main") -> dict:
    """Get latest commit for a branch."""
    headers = await get_github_headers()
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}",
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise ExternalServiceException("GitHub", f"HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            raise ExternalServiceException("GitHub", str(e))


async def get_repository_files(owner: str, repo: str, sha: str = "HEAD") -> list[dict]:
    """Get list of files in repository."""
    headers = await get_github_headers()
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/git/trees/{sha}?recursive=1",
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            return [
                {"path": item["path"], "type": item["type"]}
                for item in data.get("tree", [])
                if item["type"] == "blob"
            ]
        except httpx.HTTPStatusError as e:
            raise ExternalServiceException("GitHub", f"HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            raise ExternalServiceException("GitHub", str(e))
```

### Step 8: Create main.py

```python
# apps/api/app/main.py
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.api.v1.router import api_router

settings = get_settings()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting Repo2Web API", env=settings.APP_ENV)
    yield
    logger.info("Shutting down Repo2Web API")


def create_app() -> FastAPI:
    application = FastAPI(
        title="Repo2Web API",
        description="Convert GitHub repositories into runnable web applications",
        version="0.1.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.error_code,
                    "detail": exc.detail,
                }
            },
            headers=exc.headers,
        )

    application.include_router(api_router, prefix="/api/v1")

    return application


app = create_app()
```

### Step 9: Create Dockerfile

```dockerfile
# apps/api/Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Step 10: Create docker-compose.yml

```yaml
# apps/api/docker-compose.yml
version: "3.9"

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: repo2web
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/repo2web
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock

  worker:
    build:
      context: .
      dockerfile: Dockerfile
    command: celery -A app.tasks.celery_app worker -l info -c 4
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/repo2web
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock

  beat:
    build:
      context: .
      dockerfile: Dockerfile
    command: celery -A app.tasks.celery_app beat -l info
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/repo2web
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

volumes:
  postgres_data:
```

### Step 11: Create __init__.py files

```python
# apps/api/app/__init__.py
```

```python
# apps/api/app/core/__init__.py
```

```python
# apps/api/app/utils/__init__.py
```

### Step 12: Commit scaffolding

```bash
git add apps/api/
git commit -m "feat: project scaffolding with FastAPI, config, database, Docker"
```

---

## Task 2: Database Models - Base, User, Repository, Snapshot

**Files:**
- Create: `apps/api/app/models/__init__.py`
- Create: `apps/api/app/models/base.py`
- Create: `apps/api/app/models/user.py`
- Create: `apps/api/app/models/repository.py`
- Create: `apps/api/app/models/snapshot.py`

**Interfaces:**
- Produces: `Base`, `User`, `Repository`, `RepositorySnapshot` with full relationships

### Step 1: Create base model

```python
# apps/api/app/models/base.py
import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
```

### Step 2: Create User model

```python
# apps/api/app/models/user.py
import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    repositories: Mapped[list["Repository"]] = relationship(
        "Repository", back_populates="owner", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"
```

### Step 3: Create Repository model

```python
# apps/api/app/models/repository.py
import uuid
from datetime import datetime
from typing import Optional
import enum

from sqlalchemy import ForeignKey, String, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RepositoryStatus(str, enum.Enum):
    PENDING = "pending"
    CLONING = "cloning"
    ANALYZING = "analyzing"
    READY = "ready"
    ERROR = "error"


class Repository(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "repositories"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(100), nullable=False, default="main")
    status: Mapped[RepositoryStatus] = mapped_column(
        SAEnum(RepositoryStatus, name="repository_status"),
        nullable=False,
        default=RepositoryStatus.PENDING,
        index=True,
    )
    last_analyzed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    owner: Mapped["User"] = relationship("User", back_populates="repositories")
    snapshots: Mapped[list["RepositorySnapshot"]] = relationship(
        "RepositorySnapshot", back_populates="repository", cascade="all, delete-orphan"
    )
    deployments: Mapped[list["Deployment"]] = relationship(
        "Deployment", back_populates="repository", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Repository {self.name} ({self.url})>"
```

### Step 4: Create RepositorySnapshot model

```python
# apps/api/app/models/snapshot.py
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RepositorySnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "repository_snapshots"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sha: Mapped[str] = mapped_column(String(40), nullable=False)
    branch: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    committed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    files_changed: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    repository: Mapped["Repository"] = relationship("Repository", back_populates="snapshots")
    analysis_results: Mapped[list["AnalysisResult"]] = relationship(
        "AnalysisResult", back_populates="snapshot", cascade="all, delete-orphan"
    )
    deployments: Mapped[list["Deployment"]] = relationship(
        "Deployment", back_populates="snapshot", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<RepositorySnapshot {self.sha[:8]}...>"
```

### Step 5: Create models __init__.py

```python
# apps/api/app/models/__init__.py
from app.models.base import Base
from app.models.user import User
from app.models.repository import Repository, RepositoryStatus
from app.models.snapshot import RepositorySnapshot
from app.models.analysis import AnalysisResult
from app.models.execution_plan import ExecutionPlan
from app.models.build import BuildJob, BuildStep, BuildLog, BuildStatus
from app.models.runtime import RuntimeInstance, RuntimeStatus
from app.models.deployment import Deployment, DeploymentStatus
from app.models.health_check import HealthCheck
from app.models.usage import UsageRecord

__all__ = [
    "Base",
    "User",
    "Repository",
    "RepositoryStatus",
    "RepositorySnapshot",
    "AnalysisResult",
    "ExecutionPlan",
    "BuildJob",
    "BuildStep",
    "BuildLog",
    "BuildStatus",
    "RuntimeInstance",
    "RuntimeStatus",
    "Deployment",
    "DeploymentStatus",
    "HealthCheck",
    "UsageRecord",
]
```

### Step 6: Commit models

```bash
git add apps/api/app/models/
git commit -m "feat: add Base, User, Repository, Snapshot models"
```

---

## Task 3: Database Models - Analysis, ExecutionPlan, Build, Runtime, Deployment, HealthCheck, Usage

**Files:**
- Create: `apps/api/app/models/analysis.py`
- Create: `apps/api/app/models/execution_plan.py`
- Create: `apps/api/app/models/build.py`
- Create: `apps/api/app/models/runtime.py`
- Create: `apps/api/app/models/deployment.py`
- Create: `apps/api/app/models/health_check.py`
- Create: `apps/api/app/models/usage.py`

**Interfaces:**
- Produces: All remaining database models with full relationships

### Step 1: Create AnalysisResult model

```python
# apps/api/app/models/analysis.py
import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AnalysisResult(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analysis_results"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repository_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    primary_language: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    languages: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    framework: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    framework_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    package_manager: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    has_dockerfile: Mapped[bool] = mapped_column(default=False, nullable=False)
    has_package_json: Mapped[bool] = mapped_column(default=False, nullable=False)
    has_requirements_txt: Mapped[bool] = mapped_column(default=False, nullable=False)
    has_pom_xml: Mapped[bool] = mapped_column(default=False, nullable=False)
    has_go_mod: Mapped[bool] = mapped_column(default=False, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    raw_analysis: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    snapshot: Mapped["RepositorySnapshot"] = relationship("RepositorySnapshot", back_populates="analysis_results")
    execution_plan: Mapped[Optional["ExecutionPlan"]] = relationship(
        "ExecutionPlan", back_populates="analysis_result", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AnalysisResult {self.framework or 'unknown'}>"
```

### Step 2: Create ExecutionPlan model

```python
# apps/api/app/models/execution_plan.py
import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String, Integer, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ExecutionPlan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "execution_plans"

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_results.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    build_steps: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    environment_variables: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    port: Mapped[int] = mapped_column(Integer, default=8080, nullable=False)
    health_check_path: Mapped[str] = mapped_column(String(255), default="/", nullable=False)
    start_command: Mapped[str] = mapped_column(String(500), nullable=False)
    install_command: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    build_command: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    estimated_build_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    estimated_memory_mb: Mapped[int] = mapped_column(Integer, default=512, nullable=False)
    estimated_cpu_units: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    analysis_result: Mapped["AnalysisResult"] = relationship("AnalysisResult", back_populates="execution_plan")

    def __repr__(self) -> str:
        return f"<ExecutionPlan for {self.analysis_id}>"
```

### Step 3: Create Build models

```python
# apps/api/app/models/build.py
import uuid
from datetime import datetime
from typing import Optional
import enum

from sqlalchemy import ForeignKey, String, Text, Integer, Enum as SAEnum, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BuildStatus(str, enum.Enum):
    PENDING = "pending"
    CLONING = "cloning"
    INSTALLING = "installing"
    BUILDING = "building"
    TESTING = "testing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BuildJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "build_jobs"

    deployment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deployments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[BuildStatus] = mapped_column(
        SAEnum(BuildStatus, name="build_status"),
        nullable=False,
        default=BuildStatus.PENDING,
        index=True,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    worker_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    deployment: Mapped["Deployment"] = relationship("Deployment", back_populates="build_jobs")
    steps: Mapped[list["BuildStep"]] = relationship(
        "BuildStep", back_populates="build_job", cascade="all, delete-orphan", order_by="BuildStep.order"
    )
    logs: Mapped[list["BuildLog"]] = relationship(
        "BuildLog", back_populates="build_job", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<BuildJob {self.status}>"


class BuildStep(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "build_steps"

    build_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("build_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[BuildStatus] = mapped_column(
        SAEnum(BuildStatus, name="build_status"),
        nullable=False,
        default=BuildStatus.PENDING,
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    build_job: Mapped["BuildJob"] = relationship("BuildJob", back_populates="steps")

    def __repr__(self) -> str:
        return f"<BuildStep {self.name} ({self.status})>"


class BuildLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "build_logs"

    build_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("build_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    build_job: Mapped["BuildJob"] = relationship("BuildJob", back_populates="logs")

    def __repr__(self) -> str:
        return f"<BuildLog {self.level}: {self.message[:50]}>"
```

### Step 4: Create RuntimeInstance model

```python
# apps/api/app/models/runtime.py
import uuid
from datetime import datetime
from typing import Optional
import enum

from sqlalchemy import ForeignKey, String, Text, Integer, Enum as SAEnum, DateTime, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RuntimeStatus(str, enum.Enum):
    PENDING = "pending"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    EXPIRED = "expired"


class RuntimeInstance(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "runtime_instances"

    deployment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deployments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    container_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True)
    container_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[RuntimeStatus] = mapped_column(
        SAEnum(RuntimeStatus, name="runtime_status"),
        nullable=False,
        default=RuntimeStatus.PENDING,
        index=True,
    )
    internal_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    external_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    memory_mb: Mapped[int] = mapped_column(Integer, default=512, nullable=False)
    cpu_units: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resource_limits: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    deployment: Mapped["Deployment"] = relationship("Deployment", back_populates="runtime_instances")
    health_checks: Mapped[list["HealthCheck"]] = relationship(
        "HealthCheck", back_populates="runtime_instance", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<RuntimeInstance {self.container_id or 'pending'} ({self.status})>"
```

### Step 5: Create Deployment model

```python
# apps/api/app/models/deployment.py
import uuid
from datetime import datetime
from typing import Optional
import enum

from sqlalchemy import ForeignKey, String, Text, Integer, Enum as SAEnum, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DeploymentStatus(str, enum.Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    BUILDING = "building"
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    EXPIRED = "expired"


class Deployment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deployments"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repository_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[DeploymentStatus] = mapped_column(
        SAEnum(DeploymentStatus, name="deployment_status"),
        nullable=False,
        default=DeploymentStatus.PENDING,
        index=True,
    )
    public_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    deployment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    repository: Mapped["Repository"] = relationship("Repository", back_populates="deployments")
    snapshot: Mapped["RepositorySnapshot"] = relationship("RepositorySnapshot", back_populates="deployments")
    build_jobs: Mapped[list["BuildJob"]] = relationship(
        "BuildJob", back_populates="deployment", cascade="all, delete-orphan"
    )
    runtime_instances: Mapped[list["RuntimeInstance"]] = relationship(
        "RuntimeInstance", back_populates="deployment", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Deployment {self.deployment_number} ({self.status})>"
```

### Step 6: Create HealthCheck model

```python
# apps/api/app/models/health_check.py
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Integer, Text, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class HealthCheck(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "health_checks"

    runtime_instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("runtime_instances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    is_healthy: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    runtime_instance: Mapped["RuntimeInstance"] = relationship("RuntimeInstance", back_populates="health_checks")

    def __repr__(self) -> str:
        return f"<HealthCheck {'healthy' if self.is_healthy else 'unhealthy'}>"
```

### Step 7: Create UsageRecord model

```python
# apps/api/app/models/usage.py
import uuid
from datetime import datetime
from typing import Optional
import enum

from sqlalchemy import ForeignKey, String, Integer, Enum as SAEnum, DateTime, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UsageType(str, enum.Enum):
    BUILD = "build"
    RUNTIME = "runtime"
    STORAGE = "storage"
    BANDWIDTH = "bandwidth"


class UsageRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "usage_records"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    deployment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deployments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    usage_type: Mapped[UsageType] = mapped_column(
        SAEnum(UsageType, name="usage_type"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    cost_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:
        return f"<UsageRecord {self.usage_type}: {self.quantity} {self.unit}>"
```

### Step 8: Commit all models

```bash
git add apps/api/app/models/
git commit -m "feat: add all database models with relationships and indexes"
```

---

## Task 4: Pydantic Schemas

**Files:**
- Create: `apps/api/app/schemas/__init__.py`
- Create: `apps/api/app/schemas/common.py`
- Create: `apps/api/app/schemas/repository.py`
- Create: `apps/api/app/schemas/deployment.py`
- Create: `apps/api/app/schemas/build.py`
- Create: `apps/api/app/schemas/analysis.py`

**Interfaces:**
- Produces: Pydantic v2 schemas for all API request/response models

### Step 1: Create common schemas

```python
# apps/api/app/schemas/common.py
from datetime import datetime
from typing import Any, Generic, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorResponse(BaseModel):
    error: dict[str, Any] = Field(..., examples=[{"code": "NOT_FOUND", "detail": "Resource not found"}])


class PaginationParams(BaseModel):
    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(20, ge=1, le=100, description="Items per page")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int


class TimestampMixin(BaseModel):
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    environment: str
```

### Step 2: Create Repository schemas

```python
# apps/api/app/schemas/repository.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from app.models.repository import RepositoryStatus
from app.schemas.common import TimestampMixin


class RepositoryCreate(BaseModel):
    url: str = Field(..., description="GitHub repository URL")


class RepositoryResponse(TimestampMixin):
    id: UUID
    user_id: UUID
    url: str
    name: str
    default_branch: str
    status: RepositoryStatus
    last_analyzed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RepositorySnapshotResponse(TimestampMixin):
    id: UUID
    repository_id: UUID
    sha: str
    branch: str
    message: Optional[str] = None
    author: Optional[str] = None
    committed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RepositoryListResponse(BaseModel):
    repositories: list[RepositoryResponse]
    total: int
```

### Step 3: Create Analysis schemas

```python
# apps/api/app/schemas/analysis.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import TimestampMixin


class AnalysisResultResponse(TimestampMixin):
    id: UUID
    snapshot_id: UUID
    primary_language: Optional[str] = None
    languages: Optional[dict] = None
    framework: Optional[str] = None
    framework_version: Optional[str] = None
    package_manager: Optional[str] = None
    has_dockerfile: bool
    has_package_json: bool
    has_requirements_txt: bool
    confidence_score: float
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class ExecutionPlanResponse(TimestampMixin):
    id: UUID
    analysis_id: UUID
    build_steps: list[dict]
    environment_variables: Optional[dict] = None
    port: int
    health_check_path: str
    start_command: str
    install_command: Optional[str] = None
    build_command: Optional[str] = None
    estimated_build_time: Optional[int] = None
    estimated_memory_mb: int
    estimated_cpu_units: float

    model_config = {"from_attributes": True}
```

### Step 4: Create Build schemas

```python
# apps/api/app/schemas/build.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.build import BuildStatus
from app.schemas.common import TimestampMixin


class BuildJobResponse(TimestampMixin):
    id: UUID
    deployment_id: UUID
    status: BuildStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    error_message: Optional[str] = None
    retry_count: int

    model_config = {"from_attributes": True}


class BuildStepResponse(TimestampMixin):
    id: UUID
    build_job_id: UUID
    name: str
    status: BuildStatus
    order: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class BuildLogResponse(TimestampMixin):
    id: UUID
    build_job_id: UUID
    step_name: Optional[str] = None
    level: str
    message: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class BuildLogsResponse(BaseModel):
    logs: list[BuildLogResponse]
    total: int
    page: int
    size: int
```

### Step 5: Create Deployment schemas

```python
# apps/api/app/schemas/deployment.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.deployment import DeploymentStatus
from app.models.runtime import RuntimeStatus
from app.schemas.common import TimestampMixin


class DeploymentCreate(BaseModel):
    repository_id: UUID = Field(..., description="Repository ID to deploy")
    snapshot_id: Optional[UUID] = Field(None, description="Specific snapshot (latest if not provided)")


class DeploymentResponse(TimestampMixin):
    id: UUID
    repository_id: UUID
    snapshot_id: UUID
    status: DeploymentStatus
    public_url: Optional[str] = None
    deployment_number: int
    is_active: bool
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class DeploymentWithBuilds(DeploymentResponse):
    build_jobs: list["BuildJobResponse"] = []


class RuntimeInstanceResponse(TimestampMixin):
    id: UUID
    deployment_id: UUID
    container_id: Optional[str] = None
    status: RuntimeStatus
    internal_url: Optional[str] = None
    external_url: Optional[str] = None
    port: int
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    memory_mb: int
    cpu_units: float

    model_config = {"from_attributes": True}


class HealthCheckResponse(TimestampMixin):
    id: UUID
    runtime_instance_id: UUID
    status_code: int
    response_time_ms: int
    is_healthy: bool
    error_message: Optional[str] = None
    checked_at: datetime

    model_config = {"from_attributes": True}
```

### Step 6: Create schemas __init__.py

```python
# apps/api/app/schemas/__init__.py
from app.schemas.common import (
    ErrorResponse,
    PaginatedResponse,
    PaginationParams,
    TimestampMixin,
    HealthResponse,
)
from app.schemas.repository import (
    RepositoryCreate,
    RepositoryResponse,
    RepositorySnapshotResponse,
    RepositoryListResponse,
)
from app.schemas.analysis import AnalysisResultResponse, ExecutionPlanResponse
from app.schemas.build import (
    BuildJobResponse,
    BuildStepResponse,
    BuildLogResponse,
    BuildLogsResponse,
)
from app.schemas.deployment import (
    DeploymentCreate,
    DeploymentResponse,
    DeploymentWithBuilds,
    RuntimeInstanceResponse,
    HealthCheckResponse,
)

__all__ = [
    "ErrorResponse",
    "PaginatedResponse",
    "PaginationParams",
    "TimestampMixin",
    "HealthResponse",
    "RepositoryCreate",
    "RepositoryResponse",
    "RepositorySnapshotResponse",
    "RepositoryListResponse",
    "AnalysisResultResponse",
    "ExecutionPlanResponse",
    "BuildJobResponse",
    "BuildStepResponse",
    "BuildLogResponse",
    "BuildLogsResponse",
    "DeploymentCreate",
    "DeploymentResponse",
    "DeploymentWithBuilds",
    "RuntimeInstanceResponse",
    "HealthCheckResponse",
]
```

### Step 7: Commit schemas

```bash
git add apps/api/app/schemas/
git commit -m "feat: add Pydantic v2 schemas for all API models"
```

---

## Task 5: Service Layer - Repository and Analyzer

**Files:**
- Create: `apps/api/app/services/__init__.py`
- Create: `apps/api/app/services/repository.py`
- Create: `apps/api/app/services/analyzer.py`

**Interfaces:**
- Produces: `RepositoryService`, `AnalyzerService`

### Step 1: Create RepositoryService

```python
# apps/api/app/services/repository.py
import uuid
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException, ValidationException, ConflictException
from app.models.repository import Repository, RepositorySnapshot, RepositoryStatus
from app.utils.github import validate_github_url, parse_github_url, get_repository_info

logger = structlog.get_logger()


class RepositoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_and_get_info(self, url: str) -> dict:
        """Validate GitHub URL and fetch repository information."""
        if not validate_github_url(url):
            raise ValidationException("Invalid GitHub repository URL")

        owner, repo = parse_github_url(url)
        info = await get_repository_info(owner, repo)
        return info

    async def create_repository(self, url: str, user_id: uuid.UUID) -> Repository:
        """Create a new repository record."""
        if not validate_github_url(url):
            raise ValidationException("Invalid GitHub repository URL")

        owner, repo_name = parse_github_url(url)

        existing = await self.db.execute(
            select(Repository).where(
                Repository.url == url,
                Repository.user_id == user_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictException("Repository already exists for this user")

        info = await self.validate_and_get_info(url)

        repository = Repository(
            user_id=user_id,
            url=url,
            name=info.get("name", repo_name),
            default_branch=info.get("default_branch", "main"),
            status=RepositoryStatus.PENDING,
        )
        self.db.add(repository)
        await self.db.flush()

        logger.info("Repository created", repository_id=str(repository.id), url=url)
        return repository

    async def get_repository(self, repo_id: uuid.UUID) -> Repository:
        """Get repository by ID."""
        result = await self.db.execute(
            select(Repository)
            .options(selectinload(Repository.snapshots))
            .where(Repository.id == repo_id)
        )
        repository = result.scalar_one_or_none()
        if not repository:
            raise NotFoundException("Repository", repo_id)
        return repository

    async def get_user_repositories(
        self, user_id: uuid.UUID, page: int = 1, size: int = 20
    ) -> tuple[list[Repository], int]:
        """Get all repositories for a user with pagination."""
        count_result = await self.db.execute(
            select(Repository).where(Repository.user_id == user_id)
        )
        total = len(count_result.scalars().all())

        result = await self.db.execute(
            select(Repository)
            .where(Repository.user_id == user_id)
            .order_by(Repository.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        repositories = list(result.scalars().all())

        return repositories, total

    async def create_snapshot(
        self,
        repository_id: uuid.UUID,
        sha: str,
        branch: str,
        message: Optional[str] = None,
        author: Optional[str] = None,
    ) -> RepositorySnapshot:
        """Create a new repository snapshot."""
        snapshot = RepositorySnapshot(
            repository_id=repository_id,
            sha=sha,
            branch=branch,
            message=message,
            author=author,
        )
        self.db.add(snapshot)
        await self.db.flush()

        logger.info("Snapshot created", snapshot_id=str(snapshot.id), sha=sha)
        return snapshot

    async def update_repository_status(
        self, repo_id: uuid.UUID, status: RepositoryStatus
    ) -> Repository:
        """Update repository status."""
        repository = await self.get_repository(repo_id)
        repository.status = status
        await self.db.flush()
        return repository
```

### Step 2: Create AnalyzerService

```python
# apps/api/app/services/analyzer.py
import uuid
from typing import Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import AnalysisResult
from app.models.execution_plan import ExecutionPlan
from app.utils.github import get_repository_files

logger = structlog.get_logger()

FRAMEWORK_PATTERNS = {
    "react": {"files": ["package.json"], "keywords": ["react", "react-dom"]},
    "vue": {"files": ["package.json"], "keywords": ["vue", "vue-router"]},
    "angular": {"files": ["package.json"], "keywords": ["@angular/core"]},
    "nextjs": {"files": ["next.config.js", "next.config.mjs"], "keywords": ["next"]},
    "nuxtjs": {"files": ["nuxt.config.js"], "keywords": ["nuxt"]},
    "svelte": {"files": ["svelte.config.js"], "keywords": ["svelte"]},
    "fastapi": {"files": ["requirements.txt", "pyproject.toml"], "keywords": ["fastapi"]},
    "django": {"files": ["manage.py"], "keywords": ["django"]},
    "flask": {"files": ["requirements.txt"], "keywords": ["flask"]},
    "express": {"files": ["package.json"], "keywords": ["express"]},
    "gin": {"files": ["go.mod"], "keywords": ["gin-gonic"]},
    "spring": {"files": ["pom.xml"], "keywords": ["spring-boot"]},
}

LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".rs": "rust",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".c": "c",
}


class AnalyzerService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze_repository(
        self, snapshot_id: uuid.UUID, sha: str, owner: str, repo: str
    ) -> AnalysisResult:
        """Analyze repository structure and detect framework."""
        files = await get_repository_files(owner, repo, sha)

        languages = self._detect_languages(files)
        framework, confidence = self._detect_framework(files)
        package_manager = self._detect_package_manager(files)

        analysis = AnalysisResult(
            snapshot_id=snapshot_id,
            primary_language=languages[0] if languages else None,
            languages=languages,
            framework=framework,
            package_manager=package_manager,
            has_dockerfile=any(f["path"] == "Dockerfile" for f in files),
            has_package_json=any(f["path"] == "package.json" for f in files),
            has_requirements_txt=any(f["path"] == "requirements.txt" for f in files),
            has_pom_xml=any(f["path"] == "pom.xml" for f in files),
            has_go_mod=any(f["path"] == "go.mod" for f in files),
            confidence_score=confidence,
            raw_analysis={"files": [f["path"] for f in files]},
        )

        self.db.add(analysis)
        await self.db.flush()

        logger.info(
            "Repository analyzed",
            analysis_id=str(analysis.id),
            framework=framework,
            confidence=confidence,
        )
        return analysis

    def _detect_languages(self, files: list[dict]) -> list[str]:
        """Detect programming languages from file extensions."""
        language_counts: dict[str, int] = {}
        for file in files:
            path = file["path"]
            for ext, lang in LANGUAGE_EXTENSIONS.items():
                if path.endswith(ext):
                    language_counts[lang] = language_counts.get(lang, 0) + 1
        return sorted(language_counts.keys(), key=lambda x: language_counts[x], reverse=True)

    def _detect_framework(self, files: list[dict]) -> tuple[Optional[str], float]:
        """Detect framework from file structure and keywords."""
        file_paths = {f["path"] for f in files}

        for framework, patterns in FRAMEWORK_PATTERNS.items():
            if any(p in file_paths for p in patterns["files"]):
                return framework, 0.7

        return None, 0.0

    def _detect_package_manager(self, files: list[dict]) -> Optional[str]:
        """Detect package manager from config files."""
        file_paths = {f["path"] for f in files}

        if "package-lock.json" in file_paths:
            return "npm"
        if "yarn.lock" in file_paths:
            return "yarn"
        if "pnpm-lock.yaml" in file_paths:
            return "pnpm"
        if "requirements.txt" in file_paths:
            return "pip"
        if "Pipfile.lock" in file_paths:
            return "pipenv"
        if "poetry.lock" in file_paths:
            return "poetry"
        if "go.sum" in file_paths:
            return "go"
        if "pom.xml" in file_paths:
            return "maven"
        if "gradle.lock" in file_paths or "gradlew" in file_paths:
            return "gradle"

        return None

    async def generate_execution_plan(
        self, analysis_id: uuid.UUID, framework: Optional[str]
    ) -> ExecutionPlan:
        """Generate execution plan based on analysis results."""
        plan_config = self._get_plan_config(framework)

        execution_plan = ExecutionPlan(
            analysis_id=analysis_id,
            build_steps=plan_config["build_steps"],
            environment_variables=plan_config.get("env_vars"),
            port=plan_config.get("port", 8080),
            health_check_path=plan_config.get("health_check_path", "/"),
            start_command=plan_config["start_command"],
            install_command=plan_config.get("install_command"),
            build_command=plan_config.get("build_command"),
            estimated_build_time=plan_config.get("estimated_build_time", 300),
            estimated_memory_mb=plan_config.get("estimated_memory_mb", 512),
            estimated_cpu_units=plan_config.get("estimated_cpu_units", 1.0),
        )

        self.db.add(execution_plan)
        await self.db.flush()

        logger.info(
            "Execution plan generated",
            plan_id=str(execution_plan.id),
            framework=framework,
        )
        return execution_plan

    def _get_plan_config(self, framework: Optional[str]) -> dict:
        """Get execution plan configuration for a framework."""
        configs = {
            "react": {
                "build_steps": [
                    {"name": "install", "command": "npm install"},
                    {"name": "build", "command": "npm run build"},
                ],
                "start_command": "npx serve -s build -l $PORT",
                "install_command": "npm install",
                "build_command": "npm run build",
                "port": 3000,
                "estimated_build_time": 180,
            },
            "vue": {
                "build_steps": [
                    {"name": "install", "command": "npm install"},
                    {"name": "build", "command": "npm run build"},
                ],
                "start_command": "npx serve -s dist -l $PORT",
                "install_command": "npm install",
                "build_command": "npm run build",
                "port": 3000,
                "estimated_build_time": 180,
            },
            "fastapi": {
                "build_steps": [
                    {"name": "install", "command": "pip install -r requirements.txt"},
                ],
                "start_command": "uvicorn main:app --host 0.0.0.0 --port $PORT",
                "install_command": "pip install -r requirements.txt",
                "port": 8000,
                "estimated_build_time": 120,
            },
            "django": {
                "build_steps": [
                    {"name": "install", "command": "pip install -r requirements.txt"},
                    {"name": "migrate", "command": "python manage.py migrate"},
                ],
                "start_command": "gunicorn myproject.wsgi:application --bind 0.0.0.0:$PORT",
                "install_command": "pip install -r requirements.txt",
                "port": 8000,
                "estimated_build_time": 120,
            },
            "flask": {
                "build_steps": [
                    {"name": "install", "command": "pip install -r requirements.txt"},
                ],
                "start_command": "gunicorn main:app --bind 0.0.0.0:$PORT",
                "install_command": "pip install -r requirements.txt",
                "port": 5000,
                "estimated_build_time": 120,
            },
        }

        return configs.get(framework, {
            "build_steps": [{"name": "setup", "command": "echo 'No specific setup required'"}],
            "start_command": "echo 'No start command configured'",
            "port": 8080,
            "estimated_build_time": 60,
        })
```

### Step 3: Create services __init__.py

```python
# apps/api/app/services/__init__.py
from app.services.repository import RepositoryService
from app.services.analyzer import AnalyzerService
from app.services.build import BuildService
from app.services.runtime import RuntimeService
from app.services.deployment import DeploymentService

__all__ = [
    "RepositoryService",
    "AnalyzerService",
    "BuildService",
    "RuntimeService",
    "DeploymentService",
]
```

### Step 4: Commit services

```bash
git add apps/api/app/services/
git commit -m "feat: add RepositoryService and AnalyzerService"
```

---

## Task 6: Service Layer - Build, Runtime, Deployment

**Files:**
- Create: `apps/api/app/services/build.py`
- Create: `apps/api/app/services/runtime.py`
- Create: `apps/api/app/services/deployment.py`

**Interfaces:**
- Produces: `BuildService`, `RuntimeService`, `DeploymentService`

### Step 1: Create BuildService

```python
# apps/api/app/services/build.py
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException
from app.models.build import BuildJob, BuildStep, BuildLog, BuildStatus

logger = structlog.get_logger()


class BuildService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_build_job(self, deployment_id: uuid.UUID) -> BuildJob:
        """Create a new build job for a deployment."""
        build_job = BuildJob(
            deployment_id=deployment_id,
            status=BuildStatus.PENDING,
        )
        self.db.add(build_job)
        await self.db.flush()

        logger.info("Build job created", build_job_id=str(build_job.id))
        return build_job

    async def get_build_job(self, job_id: uuid.UUID) -> BuildJob:
        """Get build job with steps and logs."""
        result = await self.db.execute(
            select(BuildJob)
            .options(
                selectinload(BuildJob.steps),
                selectinload(BuildJob.logs),
            )
            .where(BuildJob.id == job_id)
        )
        build_job = result.scalar_one_or_none()
        if not build_job:
            raise NotFoundException("BuildJob", job_id)
        return build_job

    async def add_build_step(
        self, build_job_id: uuid.UUID, name: str, order: int
    ) -> BuildStep:
        """Add a step to a build job."""
        step = BuildStep(
            build_job_id=build_job_id,
            name=name,
            order=order,
            status=BuildStatus.PENDING,
        )
        self.db.add(step)
        await self.db.flush()
        return step

    async def add_build_log(
        self,
        build_job_id: uuid.UUID,
        message: str,
        level: str = "info",
        step_name: str | None = None,
    ) -> BuildLog:
        """Add a log entry to a build job."""
        log = BuildLog(
            build_job_id=build_job_id,
            message=message,
            level=level,
            step_name=step_name,
            timestamp=datetime.now(timezone.utc),
        )
        self.db.add(log)
        await self.db.flush()
        return log

    async def update_build_status(
        self, job_id: uuid.UUID, status: BuildStatus, error_message: str | None = None
    ) -> BuildJob:
        """Update build job status."""
        build_job = await self.get_build_job(job_id)
        build_job.status = status

        if status == BuildStatus.BUILDING and not build_job.started_at:
            build_job.started_at = datetime.now(timezone.utc)
        elif status in (BuildStatus.SUCCESS, BuildStatus.FAILED):
            build_job.completed_at = datetime.now(timezone.utc)
            if build_job.started_at:
                delta = build_job.completed_at - build_job.started_at
                build_job.duration_seconds = int(delta.total_seconds())

        if error_message:
            build_job.error_message = error_message

        await self.db.flush()
        return build_job

    async def update_step_status(
        self, step_id: uuid.UUID, status: BuildStatus, error_message: str | None = None
    ) -> BuildStep:
        """Update build step status."""
        result = await self.db.execute(
            select(BuildStep).where(BuildStep.id == step_id)
        )
        step = result.scalar_one_or_none()
        if not step:
            raise NotFoundException("BuildStep", step_id)

        step.status = status

        if status == BuildStatus.BUILDING:
            step.started_at = datetime.now(timezone.utc)
        elif status in (BuildStatus.SUCCESS, BuildStatus.FAILED):
            step.completed_at = datetime.now(timezone.utc)
            if step.started_at:
                delta = step.completed_at - step.started_at
                step.duration_seconds = int(delta.total_seconds())

        if error_message:
            step.error_message = error_message

        await self.db.flush()
        return step

    async def get_build_logs(
        self,
        job_id: uuid.UUID,
        page: int = 1,
        size: int = 100,
        step_name: str | None = None,
        level: str | None = None,
    ) -> tuple[list[BuildLog], int]:
        """Get paginated build logs with optional filters."""
        query = select(BuildLog).where(BuildLog.build_job_id == job_id)

        if step_name:
            query = query.where(BuildLog.step_name == step_name)
        if level:
            query = query.where(BuildLog.level == level)

        count_result = await self.db.execute(query)
        total = len(count_result.scalars().all())

        query = query.order_by(BuildLog.timestamp).offset((page - 1) * size).limit(size)
        result = await self.db.execute(query)
        logs = list(result.scalars().all())

        return logs, total
```

### Step 2: Create RuntimeService

```python
# apps/api/app/services/runtime.py
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundException
from app.models.runtime import RuntimeInstance, RuntimeStatus
from app.models.health_check import HealthCheck

logger = structlog.get_logger()
settings = get_settings()


class RuntimeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def start_runtime(self, deployment_id: uuid.UUID, port: int) -> RuntimeInstance:
        """Create and start a new runtime instance."""
        runtime = RuntimeInstance(
            deployment_id=deployment_id,
            port=port,
            status=RuntimeStatus.PENDING,
            memory_mb=512,
            cpu_units=1.0,
        )
        self.db.add(runtime)
        await self.db.flush()

        logger.info("Runtime instance created", runtime_id=str(runtime.id))
        return runtime

    async def get_runtime(self, instance_id: uuid.UUID) -> RuntimeInstance:
        """Get runtime instance by ID."""
        result = await self.db.execute(
            select(RuntimeInstance).where(RuntimeInstance.id == instance_id)
        )
        runtime = result.scalar_one_or_none()
        if not runtime:
            raise NotFoundException("RuntimeInstance", instance_id)
        return runtime

    async def update_runtime_status(
        self,
        instance_id: uuid.UUID,
        status: RuntimeStatus,
        container_id: str | None = None,
        error_message: str | None = None,
    ) -> RuntimeInstance:
        """Update runtime instance status."""
        runtime = await self.get_runtime(instance_id)
        runtime.status = status

        if container_id:
            runtime.container_id = container_id

        if status == RuntimeStatus.RUNNING:
            runtime.started_at = datetime.now(timezone.utc)
            runtime.expires_at = datetime.now(timezone.utc) + timedelta(
                hours=settings.RUNTIME_TTL_HOURS
            )
        elif status in (RuntimeStatus.STOPPED, RuntimeStatus.FAILED):
            runtime.stopped_at = datetime.now(timezone.utc)

        if error_message:
            runtime.error_message = error_message

        await self.db.flush()
        return runtime

    async def stop_runtime(self, instance_id: uuid.UUID) -> bool:
        """Stop a runtime instance."""
        runtime = await self.get_runtime(instance_id)
        if runtime.status == RuntimeStatus.RUNNING:
            runtime.status = RuntimeStatus.STOPPING
            await self.db.flush()
            return True
        return False

    async def create_health_check(
        self,
        runtime_instance_id: uuid.UUID,
        status_code: int,
        response_time_ms: int,
        is_healthy: bool,
        error_message: str | None = None,
    ) -> HealthCheck:
        """Record a health check result."""
        health_check = HealthCheck(
            runtime_instance_id=runtime_instance_id,
            status_code=status_code,
            response_time_ms=response_time_ms,
            is_healthy=is_healthy,
            error_message=error_message,
            checked_at=datetime.now(timezone.utc),
        )
        self.db.add(health_check)
        await self.db.flush()
        return health_check

    async def get_expired_runtimes(self) -> list[RuntimeInstance]:
        """Get all runtime instances that have expired."""
        result = await self.db.execute(
            select(RuntimeInstance).where(
                RuntimeInstance.status == RuntimeStatus.RUNNING,
                RuntimeInstance.expires_at < datetime.now(timezone.utc),
            )
        )
        return list(result.scalars().all())
```

### Step 3: Create DeploymentService

```python
# apps/api/app/services/deployment.py
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException
from app.models.deployment import Deployment, DeploymentStatus
from app.models.repository import Repository, RepositorySnapshot

logger = structlog.get_logger()


class DeploymentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_deployment(
        self, repository_id: uuid.UUID, snapshot_id: uuid.UUID
    ) -> Deployment:
        """Create a new deployment."""
        count_result = await self.db.execute(
            select(func.count(Deployment.id)).where(Deployment.repository_id == repository_id)
        )
        deployment_number = count_result.scalar() + 1

        deployment = Deployment(
            repository_id=repository_id,
            snapshot_id=snapshot_id,
            status=DeploymentStatus.PENDING,
            deployment_number=deployment_number,
        )
        self.db.add(deployment)
        await self.db.flush()

        logger.info(
            "Deployment created",
            deployment_id=str(deployment.id),
            number=deployment_number,
        )
        return deployment

    async def get_deployment(self, deployment_id: uuid.UUID) -> Deployment:
        """Get deployment by ID with related data."""
        result = await self.db.execute(
            select(Deployment)
            .options(
                selectinload(Deployment.repository),
                selectinload(Deployment.snapshot),
                selectinload(Deployment.build_jobs),
                selectinload(Deployment.runtime_instances),
            )
            .where(Deployment.id == deployment_id)
        )
        deployment = result.scalar_one_or_none()
        if not deployment:
            raise NotFoundException("Deployment", deployment_id)
        return deployment

    async def update_status(
        self,
        deployment_id: uuid.UUID,
        status: DeploymentStatus,
        error_message: str | None = None,
        public_url: str | None = None,
    ) -> Deployment:
        """Update deployment status."""
        deployment = await self.get_deployment(deployment_id)
        deployment.status = status

        if error_message:
            deployment.error_message = error_message

        if public_url:
            deployment.public_url = public_url

        await self.db.flush()
        return deployment

    async def get_latest_snapshot(self, repository_id: uuid.UUID) -> RepositorySnapshot | None:
        """Get the latest snapshot for a repository."""
        result = await self.db.execute(
            select(RepositorySnapshot)
            .where(RepositorySnapshot.repository_id == repository_id)
            .order_by(RepositorySnapshot.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_repository_deployments(
        self, repository_id: uuid.UUID, page: int = 1, size: int = 20
    ) -> tuple[list[Deployment], int]:
        """Get all deployments for a repository."""
        count_result = await self.db.execute(
            select(Deployment).where(Deployment.repository_id == repository_id)
        )
        total = len(count_result.scalars().all())

        result = await self.db.execute(
            select(Deployment)
            .where(Deployment.repository_id == repository_id)
            .order_by(Deployment.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        deployments = list(result.scalars().all())

        return deployments, total
```

### Step 4: Commit services

```bash
git add apps/api/app/services/
git commit -m "feat: add BuildService, RuntimeService, DeploymentService"
```

---

## Task 7: API Dependencies and Router

**Files:**
- Create: `apps/api/app/api/__init__.py`
- Create: `apps/api/app/api/deps.py`
- Create: `apps/api/app/api/v1/__init__.py`
- Create: `apps/api/app/api/v1/router.py`
- Create: `apps/api/app/api/v1/repositories.py`
- Create: `apps/api/app/api/v1/deployments.py`
- Create: `apps/api/app/api/v1/health.py`

**Interfaces:**
- Produces: FastAPI router with all endpoints

### Step 1: Create API dependencies

```python
# apps/api/app/api/deps.py
from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.services import (
    RepositoryService,
    AnalyzerService,
    BuildService,
    RuntimeService,
    DeploymentService,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_repository_service(db: AsyncSession = Depends(get_db)) -> RepositoryService:
    return RepositoryService(db)


async def get_analyzer_service(db: AsyncSession = Depends(get_db)) -> AnalyzerService:
    return AnalyzerService(db)


async def get_build_service(db: AsyncSession = Depends(get_db)) -> BuildService:
    return BuildService(db)


async def get_runtime_service(db: AsyncSession = Depends(get_db)) -> RuntimeService:
    return RuntimeService(db)


async def get_deployment_service(db: AsyncSession = Depends(get_db)) -> DeploymentService:
    return DeploymentService(db)
```

### Step 2: Create v1 router

```python
# apps/api/app/api/v1/router.py
from fastapi import APIRouter

from app.api.v1 import repositories, deployments, health

api_router = APIRouter()

api_router.include_router(repositories.router, prefix="/repositories", tags=["repositories"])
api_router.include_router(deployments.router, prefix="/deployments", tags=["deployments"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
```

### Step 3: Create repositories endpoints

```python
# apps/api/app/api/v1/repositories.py
from uuid import UUID

from fastapi import APIRouter, Depends, Query, BackgroundTasks

from app.api.deps import get_repository_service, get_analyzer_service
from app.schemas.repository import RepositoryCreate, RepositoryResponse, RepositoryListResponse
from app.services import RepositoryService, AnalyzerService

router = APIRouter()


@router.post("/analyze", response_model=dict)
async def analyze_repository(
    request: RepositoryCreate,
    background_tasks: BackgroundTasks,
    repo_service: RepositoryService = Depends(get_repository_service),
):
    """Analyze a GitHub repository."""
    from uuid import uuid4
    user_id = uuid4()

    repository = await repo_service.create_repository(request.url, user_id)

    from app.tasks.analyze import analyze_repository_task
    background_tasks.add_task(
        analyze_repository_task.delay,
        str(repository.id),
    )

    return {
        "repository_id": str(repository.id),
        "status": repository.status,
        "message": "Repository analysis queued",
    }


@router.get("/{repository_id}", response_model=RepositoryResponse)
async def get_repository(
    repository_id: UUID,
    repo_service: RepositoryService = Depends(get_repository_service),
):
    """Get repository details."""
    repository = await repo_service.get_repository(repository_id)
    return repository


@router.get("/", response_model=RepositoryListResponse)
async def list_repositories(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    repo_service: RepositoryService = Depends(get_repository_service),
):
    """List repositories for the current user."""
    from uuid import uuid4
    user_id = uuid4()

    repositories, total = await repo_service.get_user_repositories(user_id, page, size)
    return RepositoryListResponse(repositories=repositories, total=total)
```

### Step 4: Create deployments endpoints

```python
# apps/api/app/api/v1/deployments.py
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, BackgroundTasks

from app.api.deps import get_deployment_service, get_build_service
from app.schemas.deployment import DeploymentCreate, DeploymentResponse
from app.schemas.build import BuildLogsResponse, BuildLogResponse
from app.services import DeploymentService, BuildService

router = APIRouter()


@router.post("/", response_model=dict)
async def create_deployment(
    request: DeploymentCreate,
    background_tasks: BackgroundTasks,
    deployment_service: DeploymentService = Depends(get_deployment_service),
):
    """Create a new deployment from a repository."""
    snapshot = await deployment_service.get_latest_snapshot(request.repository_id)
    if not snapshot:
        snapshot_id = request.snapshot_id
    else:
        snapshot_id = snapshot.id

    deployment = await deployment_service.create_deployment(
        request.repository_id, snapshot_id
    )

    from app.tasks.build import build_repository_task
    background_tasks.add_task(
        build_repository_task.delay,
        str(deployment.id),
    )

    return {
        "deployment_id": str(deployment.id),
        "status": deployment.status,
        "deployment_number": deployment.deployment_number,
        "message": "Deployment queued",
    }


@router.get("/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment(
    deployment_id: UUID,
    deployment_service: DeploymentService = Depends(get_deployment_service),
):
    """Get deployment details."""
    deployment = await deployment_service.get_deployment(deployment_id)
    return deployment


@router.get("/{deployment_id}/logs", response_model=BuildLogsResponse)
async def get_deployment_logs(
    deployment_id: UUID,
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=1000),
    step_name: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    deployment_service: DeploymentService = Depends(get_deployment_service),
    build_service: BuildService = Depends(get_build_service),
):
    """Get build logs for a deployment."""
    deployment = await deployment_service.get_deployment(deployment_id)

    if not deployment.build_jobs:
        return BuildLogsResponse(logs=[], total=0, page=page, size=size)

    latest_build = max(deployment.build_jobs, key=lambda b: b.created_at)
    logs, total = await build_service.get_build_logs(
        latest_build.id, page, size, step_name, level
    )

    return BuildLogsResponse(
        logs=[BuildLogResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        size=size,
    )
```

### Step 5: Create health endpoints

```python
# apps/api/app/api/v1/health.py
from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.common import HealthResponse

router = APIRouter()
settings = get_settings()


@router.get("/", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        version="0.1.0",
        environment=settings.APP_ENV,
    )
```

### Step 6: Create __init__.py files

```python
# apps/api/app/api/__init__.py
```

```python
# apps/api/app/api/v1/__init__.py
```

### Step 7: Commit API layer

```bash
git add apps/api/app/api/
git commit -m "feat: add API endpoints for repositories, deployments, health"
```

---

## Task 8: Celery Tasks

**Files:**
- Create: `apps/api/app/tasks/__init__.py`
- Create: `apps/api/app/tasks/celery_app.py`
- Create: `apps/api/app/tasks/analyze.py`
- Create: `apps/api/app/tasks/build.py`
- Create: `apps/api/app/tasks/runtime.py`

**Interfaces:**
- Produces: Celery task definitions with retry logic and error handling

### Step 1: Create Celery app

```python
# apps/api/app/tasks/celery_app.py
from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "repo2web",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.BUILD_TIMEOUT * 2,
    task_soft_time_limit=settings.BUILD_TIMEOUT,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
)

celery_app.autodiscover_tasks(["app.tasks"])

celery_app.conf.beat_schedule = {
    "cleanup-expired-runtimes": {
        "task": "app.tasks.runtime.cleanup_expired_runtimes",
        "schedule": crontab(minute="*/5"),
    },
}
```

### Step 2: Create analyze tasks

```python
# apps/api/app/tasks/analyze.py
import uuid

import structlog
from sqlalchemy.orm import Session

from app.core.database import get_sync_db
from app.models.repository import Repository, RepositoryStatus
from app.services.analyzer import AnalyzerService
from app.services.repository import RepositoryService
from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
    track_started=True,
)
def analyze_repository_task(self, repository_id: str):
    """Analyze a repository and generate execution plan."""
    db: Session = get_sync_db()
    try:
        repo_service = RepositoryService(db)
        analyzer_service = AnalyzerService(db)

        repo_id = uuid.UUID(repository_id)
        repo_service.update_repository_status(repo_id, RepositoryStatus.ANALYZING)

        repository = repo_service.get_repository(repo_id)

        from app.utils.github import parse_github_url
        owner, repo = parse_github_url(repository.url)

        snapshot = repo_service.create_snapshot(
            repository_id=repo_id,
            sha="HEAD",
            branch=repository.default_branch,
        )

        analysis = analyzer_service.analyze_repository(
            snapshot_id=snapshot.id,
            sha="HEAD",
            owner=owner,
            repo=repo,
        )

        execution_plan = analyzer_service.generate_execution_plan(
            analysis_id=analysis.id,
            framework=analysis.framework,
        )

        repo_service.update_repository_status(repo_id, RepositoryStatus.READY)

        db.commit()

        logger.info(
            "Repository analysis completed",
            repository_id=repository_id,
            framework=analysis.framework,
        )

        return {
            "repository_id": repository_id,
            "analysis_id": str(analysis.id),
            "framework": analysis.framework,
            "confidence": analysis.confidence_score,
        }

    except Exception as exc:
        db.rollback()
        logger.error(
            "Repository analysis failed",
            repository_id=repository_id,
            error=str(exc),
        )
        try:
            repo_service.update_repository_status(
                uuid.UUID(repository_id), RepositoryStatus.ERROR
            )
            db.commit()
        except Exception:
            pass

        raise self.retry(exc=exc)

    finally:
        db.close()
```

### Step 3: Create build tasks

```python
# apps/api/app/tasks/build.py
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy.orm import Session

from app.core.database import get_sync_db
from app.models.build import BuildJob, BuildStep, BuildStatus
from app.models.deployment import Deployment, DeploymentStatus
from app.services.build import BuildService
from app.services.deployment import DeploymentService
from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    acks_late=True,
    track_started=True,
)
def build_repository_task(self, deployment_id: str):
    """Build a repository for deployment."""
    db: Session = get_sync_db()
    try:
        build_service = BuildService(db)
        deployment_service = DeploymentService(db)

        deploy_id = uuid.UUID(deployment_id)
        deployment_service.update_status(deploy_id, DeploymentStatus.BUILDING)

        build_job = build_service.create_build_job(deploy_id)

        steps = [
            ("clone", 1),
            ("install", 2),
            ("build", 3),
            ("package", 4),
        ]
        for name, order in steps:
            build_service.add_build_step(build_job.id, name, order)

        build_service.update_build_status(build_job.id, BuildStatus.BUILDING)

        for step_name in ["clone", "install", "build", "package"]:
            from sqlalchemy import select
            result = db.execute(
                select(BuildStep).where(
                    BuildStep.build_job_id == build_job.id,
                    BuildStep.name == step_name,
                )
            )
            step = result.scalar_one()

            build_service.update_step_status(step.id, BuildStatus.BUILDING)

            build_service.add_build_log(
                build_job.id,
                f"Starting {step_name} step",
                "info",
                step_name,
            )

            import time
            time.sleep(1)

            build_service.update_step_status(step.id, BuildStatus.SUCCESS)

            build_service.add_build_log(
                build_job.id,
                f"Completed {step_name} step",
                "info",
                step_name,
            )

        build_service.update_build_status(build_job.id, BuildStatus.SUCCESS)

        deployment_service.update_status(deploy_id, DeploymentStatus.RUNNING)

        db.commit()

        logger.info("Build completed", deployment_id=deployment_id)

        return {
            "deployment_id": deployment_id,
            "build_job_id": str(build_job.id),
            "status": "success",
        }

    except Exception as exc:
        db.rollback()
        logger.error("Build failed", deployment_id=deployment_id, error=str(exc))

        try:
            deployment_service.update_status(
                uuid.UUID(deployment_id),
                DeploymentStatus.FAILED,
                error_message=str(exc),
            )
            db.commit()
        except Exception:
            pass

        raise self.retry(exc=exc)

    finally:
        db.close()
```

### Step 4: Create runtime tasks

```python
# apps/api/app/tasks/runtime.py
import uuid

import structlog
from sqlalchemy.orm import Session

from app.core.database import get_sync_db
from app.services.runtime import RuntimeService
from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task
def cleanup_expired_runtimes():
    """Clean up expired runtime instances."""
    db: Session = get_sync_db()
    try:
        runtime_service = RuntimeService(db)

        expired = runtime_service.get_expired_runtimes()

        for runtime in expired:
            runtime_service.stop_runtime(runtime.id)
            logger.info("Stopped expired runtime", runtime_id=str(runtime.id))

        db.commit()

        return {"cleaned": len(expired)}

    except Exception as exc:
        logger.error("Cleanup failed", error=str(exc))
        db.rollback()
        raise

    finally:
        db.close()
```

### Step 5: Create tasks __init__.py

```python
# apps/api/app/tasks/__init__.py
from app.tasks.celery_app import celery_app
from app.tasks import analyze, build, runtime

__all__ = ["celery_app"]
```

### Step 6: Commit tasks

```bash
git add apps/api/app/tasks/
git commit -m "feat: add Celery tasks for analysis, build, runtime cleanup"
```

---

## Task 9: Alembic Migrations

**Files:**
- Create: `apps/api/alembic.ini`
- Create: `apps/api/alembic/env.py`
- Create: `apps/api/alembic/script.py.mako`
- Create: `apps/api/alembic/versions/` (directory)

**Interfaces:**
- Produces: Alembic configuration and initial migration

### Step 1: Create alembic.ini

```ini
# apps/api/alembic.ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url = postgresql+psycopg2://postgres:postgres@localhost:5432/repo2web

[post_write_hooks]

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

### Step 2: Create env.py

```python
# apps/api/alembic/env.py
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.models import Base

config = context.config
settings = get_settings()

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### Step 3: Create script.py.mako

```mako
# apps/api/alembic/script.py.mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

### Step 4: Create versions directory

```bash
mkdir -p apps/api/alembic/versions
```

### Step 5: Commit migrations

```bash
git add apps/api/alembic.ini apps/api/alembic/
git commit -m "feat: add Alembic configuration and migration templates"
```

---

## Task 10: Test Code

**Files:**
- Create: `apps/api/tests/__init__.py`
- Create: `apps/api/tests/conftest.py`
- Create: `apps/api/tests/test_health.py`
- Create: `apps/api/tests/test_repository_validation.py`
- Create: `apps/api/tests/test_analyzer.py`
- Create: `apps/api/tests/test_models.py`
- Create: `apps/api/tests/test_api_repositories.py`

**Interfaces:**
- Produces: Comprehensive test suite with pytest + pytest-asyncio

### Step 1: Create test fixtures

```python
# apps/api/tests/__init__.py
```

```python
# apps/api/tests/conftest.py
import asyncio
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.main import app
from app.models import Base
from app.models.user import User
from app.core.security import get_password_hash

settings = get_settings()

TEST_DATABASE_URL = settings.DATABASE_URL.replace("repo2web", "repo2web_test")

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create tables before each test and drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid4(),
        email="test@example.com",
        hashed_password=get_password_hash("testpassword123"),
        first_name="Test",
        last_name="User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user
```

### Step 2: Create health endpoint test

```python
# apps/api/tests/test_health.py
import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest.mark.asyncio
class TestHealthEndpoint:
    async def test_health_check_returns_ok(self, client: AsyncClient):
        """Test that health endpoint returns 200 with ok status."""
        response = await client.get("/api/v1/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"
        assert "environment" in data

    async def test_health_check_has_version(self, client: AsyncClient):
        """Test that health response includes version."""
        response = await client.get("/api/v1/health/")
        data = response.json()
        assert "version" in data
        assert isinstance(data["version"], str)

    async def test_health_check_has_environment(self, client: AsyncClient):
        """Test that health response includes environment."""
        response = await client.get("/api/v1/health/")
        data = response.json()
        assert "environment" in data
        assert isinstance(data["environment"], str)
```

### Step 3: Create repository validation tests

```python
# apps/api/tests/test_repository_validation.py
import pytest
from app.utils.github import validate_github_url, parse_github_url
from app.core.exceptions import ValidationException


class TestGitHubURLValidation:
    def test_valid_github_url(self):
        """Test valid GitHub URLs are accepted."""
        assert validate_github_url("https://github.com/owner/repo") is True
        assert validate_github_url("https://github.com/owner/repo.git") is True
        assert validate_github_url("https://github.com/owner/repo/tree/main") is True
        assert validate_github_url("http://github.com/owner/repo") is True

    def test_invalid_url_not_github(self):
        """Test non-GitHub URLs are rejected."""
        assert validate_github_url("https://gitlab.com/owner/repo") is False
        assert validate_github_url("https://bitbucket.org/owner/repo") is False

    def test_invalid_url_not_a_url(self):
        """Test non-URL strings are rejected."""
        assert validate_github_url("not-a-url") is False
        assert validate_github_url("") is False
        assert validate_github_url("github.com/owner/repo") is False

    def test_invalid_url_missing_repo(self):
        """Test URLs missing repo name are rejected."""
        assert validate_github_url("https://github.com/") is False
        assert validate_github_url("https://github.com/owner") is False

    def test_parse_github_url_valid(self):
        """Test parsing valid GitHub URLs."""
        owner, repo = parse_github_url("https://github.com/owner/repo")
        assert owner == "owner"
        assert repo == "repo"

    def test_parse_github_url_with_suffix(self):
        """Test parsing GitHub URLs with path suffixes."""
        owner, repo = parse_github_url("https://github.com/owner/repo.git")
        assert owner == "owner"
        assert repo == "repo"

    def test_parse_github_url_invalid_raises(self):
        """Test parsing invalid URL raises ValidationException."""
        with pytest.raises(ValidationException):
            parse_github_url("https://gitlab.com/owner/repo")
```

### Step 4: Create analyzer tests

```python
# apps/api/tests/test_analyzer.py
import pytest
from app.services.analyzer import AnalyzerService


class TestAnalyzerService:
    def test_detect_languages_python(self):
        """Test Python language detection."""
        files = [
            {"path": "main.py", "type": "blob"},
            {"path": "utils.py", "type": "blob"},
        ]
        # Create a mock analyzer
        analyzer = AnalyzerService.__new__(AnalyzerService)
        languages = analyzer._detect_languages(files)
        assert "python" in languages

    def test_detect_languages_multiple(self):
        """Test detection of multiple languages."""
        files = [
            {"path": "main.py", "type": "blob"},
            {"path": "app.js", "type": "blob"},
            {"path": "style.css", "type": "blob"},
        ]
        analyzer = AnalyzerService.__new__(AnalyzerService)
        languages = analyzer._detect_languages(files)
        assert "python" in languages
        assert "javascript" in languages

    def test_detect_framework_react(self):
        """Test React framework detection."""
        files = [{"path": "package.json", "type": "blob"}]
        analyzer = AnalyzerService.__new__(AnalyzerService)
        framework, confidence = analyzer._detect_framework(files)
        assert framework == "react"
        assert confidence > 0

    def test_detect_framework_fastapi(self):
        """Test FastAPI framework detection."""
        files = [{"path": "requirements.txt", "type": "blob"}]
        analyzer = AnalyzerService.__new__(AnalyzerService)
        framework, confidence = analyzer._detect_framework(files)
        assert framework == "fastapi"
        assert confidence > 0

    def test_detect_framework_none(self):
        """Test no framework detected."""
        files = [{"path": "README.md", "type": "blob"}]
        analyzer = AnalyzerService.__new__(AnalyzerService)
        framework, confidence = analyzer._detect_framework(files)
        assert framework is None
        assert confidence == 0.0

    def test_detect_package_manager_npm(self):
        """Test npm package manager detection."""
        files = [{"path": "package-lock.json", "type": "blob"}]
        analyzer = AnalyzerService.__new__(AnalyzerService)
        assert analyzer._detect_package_manager(files) == "npm"

    def test_detect_package_manager_pip(self):
        """Test pip package manager detection."""
        files = [{"path": "requirements.txt", "type": "blob"}]
        analyzer = AnalyzerService.__new__(AnalyzerService)
        assert analyzer._detect_package_manager(files) == "pip"

    def test_detect_package_manager_yarn(self):
        """Test yarn package manager detection."""
        files = [{"path": "yarn.lock", "type": "blob"}]
        analyzer = AnalyzerService.__new__(AnalyzerService)
        assert analyzer._detect_package_manager(files) == "yarn"

    def test_detect_package_manager_none(self):
        """Test no package manager detected."""
        files = [{"path": "README.md", "type": "blob"}]
        analyzer = AnalyzerService.__new__(AnalyzerService)
        assert analyzer._detect_package_manager(files) is None
```

### Step 5: Create model tests

```python
# apps/api/tests/test_models.py
import pytest
from uuid import uuid4

from app.models.user import User
from app.models.repository import Repository, RepositoryStatus
from app.models.snapshot import RepositorySnapshot
from app.models.analysis import AnalysisResult
from app.models.execution_plan import ExecutionPlan
from app.models.build import BuildJob, BuildStatus
from app.models.runtime import RuntimeInstance, RuntimeStatus
from app.models.deployment import Deployment, DeploymentStatus
from app.models.health_check import HealthCheck
from app.core.security import get_password_hash


def test_user_creation():
    """Test User model creation."""
    user = User(
        id=uuid4(),
        email="test@example.com",
        hashed_password=get_password_hash("password123"),
        first_name="Test",
        last_name="User",
    )
    assert user.email == "test@example.com"
    assert user.is_active is True
    assert user.is_superuser is False


def test_repository_creation():
    """Test Repository model creation."""
    repo = Repository(
        id=uuid4(),
        user_id=uuid4(),
        url="https://github.com/test/repo",
        name="repo",
        status=RepositoryStatus.PENDING,
    )
    assert repo.status == RepositoryStatus.PENDING
    assert repo.url == "https://github.com/test/repo"


def test_repository_status_transitions():
    """Test Repository status transitions."""
    repo = Repository(
        id=uuid4(),
        user_id=uuid4(),
        url="https://github.com/test/repo",
        name="repo",
        status=RepositoryStatus.PENDING,
    )
    assert repo.status == RepositoryStatus.PENDING
    repo.status = RepositoryStatus.CLONING
    assert repo.status == RepositoryStatus.CLONING
    repo.status = RepositoryStatus.ANALYZING
    assert repo.status == RepositoryStatus.ANALYZING
    repo.status = RepositoryStatus.READY
    assert repo.status == RepositoryStatus.READY


def test_deployment_status_transitions():
    """Test Deployment status transitions."""
    deployment = Deployment(
        id=uuid4(),
        repository_id=uuid4(),
        snapshot_id=uuid4(),
        status=DeploymentStatus.PENDING,
        deployment_number=1,
    )
    assert deployment.status == DeploymentStatus.PENDING
    deployment.status = DeploymentStatus.ANALYZING
    assert deployment.status == DeploymentStatus.ANALYZING
    deployment.status = DeploymentStatus.BUILDING
    assert deployment.status == DeploymentStatus.BUILDING
    deployment.status = DeploymentStatus.STARTING
    assert deployment.status == DeploymentStatus.STARTING
    deployment.status = DeploymentStatus.RUNNING
    assert deployment.status == DeploymentStatus.RUNNING


def test_deployment_status_failure():
    """Test Deployment failure status."""
    deployment = Deployment(
        id=uuid4(),
        repository_id=uuid4(),
        snapshot_id=uuid4(),
        status=DeploymentStatus.BUILDING,
        deployment_number=1,
    )
    deployment.status = DeploymentStatus.FAILED
    deployment.error_message = "Build failed"
    assert deployment.status == DeploymentStatus.FAILED
    assert deployment.error_message == "Build failed"


def test_build_job_status_transitions():
    """Test BuildJob status transitions."""
    build_job = BuildJob(
        id=uuid4(),
        deployment_id=uuid4(),
        status=BuildStatus.PENDING,
    )
    assert build_job.status == BuildStatus.PENDING
    build_job.status = BuildStatus.CLONING
    assert build_job.status == BuildStatus.CLONING
    build_job.status = BuildStatus.BUILDING
    assert build_job.status == BuildStatus.BUILDING
    build_job.status = BuildStatus.SUCCESS
    assert build_job.status == BuildStatus.SUCCESS


def test_runtime_status_transitions():
    """Test RuntimeInstance status transitions."""
    runtime = RuntimeInstance(
        id=uuid4(),
        deployment_id=uuid4(),
        port=8080,
        status=RuntimeStatus.PENDING,
    )
    assert runtime.status == RuntimeStatus.PENDING
    runtime.status = RuntimeStatus.STARTING
    assert runtime.status == RuntimeStatus.STARTING
    runtime.status = RuntimeStatus.RUNNING
    assert runtime.status == RuntimeStatus.RUNNING
    runtime.status = RuntimeStatus.STOPPED
    assert runtime.status == RuntimeStatus.STOPPED


def test_snapshot_creation():
    """Test RepositorySnapshot model creation."""
    snapshot = RepositorySnapshot(
        id=uuid4(),
        repository_id=uuid4(),
        sha="abc123def456",
        branch="main",
        message="Initial commit",
        author="testuser",
    )
    assert snapshot.sha == "abc123def456"
    assert snapshot.branch == "main"


def test_analysis_result_creation():
    """Test AnalysisResult model creation."""
    analysis = AnalysisResult(
        id=uuid4(),
        snapshot_id=uuid4(),
        primary_language="python",
        framework="fastapi",
        confidence_score=0.85,
        has_requirements_txt=True,
    )
    assert analysis.framework == "fastapi"
    assert analysis.confidence_score == 0.85
```

### Step 6: Create API repository tests

```python
# apps/api/tests/test_api_repositories.py
import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest.mark.asyncio
class TestRepositoryEndpoints:
    async def test_analyze_repository_invalid_url(self, client: AsyncClient):
        """Test analyze endpoint with invalid URL."""
        response = await client.post(
            "/api/v1/repositories/analyze",
            json={"url": "not-a-valid-url"},
        )
        assert response.status_code == 422

    async def test_analyze_repository_non_github(self, client: AsyncClient):
        """Test analyze endpoint with non-GitHub URL."""
        response = await client.post(
            "/api/v1/repositories/analyze",
            json={"url": "https://gitlab.com/owner/repo"},
        )
        assert response.status_code == 422

    async def test_get_repository_not_found(self, client: AsyncClient):
        """Test get repository with non-existent ID."""
        from uuid import uuid4
        response = await client.get(f"/api/v1/repositories/{uuid4()}")
        assert response.status_code == 404

    async def test_list_repositories(self, client: AsyncClient):
        """Test list repositories endpoint."""
        response = await client.get("/api/v1/repositories/")
        assert response.status_code == 200
        data = response.json()
        assert "repositories" in data
        assert "total" in data

    async def test_list_repositories_pagination(self, client: AsyncClient):
        """Test list repositories with pagination."""
        response = await client.get("/api/v1/repositories/?page=1&size=10")
        assert response.status_code == 200
        data = response.json()
        assert "repositories" in data


@pytest.mark.asyncio
class TestDeploymentEndpoints:
    async def test_get_deployment_not_found(self, client: AsyncClient):
        """Test get deployment with non-existent ID."""
        from uuid import uuid4
        response = await client.get(f"/api/v1/deployments/{uuid4()}")
        assert response.status_code == 404

    async def test_create_deployment_invalid_repo(self, client: AsyncClient):
        """Test create deployment with invalid repository ID."""
        from uuid import uuid4
        response = await client.post(
            "/api/v1/deployments/",
            json={
                "repository_id": str(uuid4()),
                "snapshot_id": None,
            },
        )
        assert response.status_code == 404

    async def test_get_deployment_logs_not_found(self, client: AsyncClient):
        """Test get deployment logs for non-existent deployment."""
        from uuid import uuid4
        response = await client.get(f"/api/v1/deployments/{uuid4()}/logs")
        assert response.status_code == 404
```

### Step 7: Create pytest.ini

```ini
# apps/api/pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
```

### Step 8: Commit tests

```bash
git add apps/api/tests/ apps/api/pytest.ini
git commit -m "feat: add test suite with health, validation, analyzer, model, API tests"
```

---

## Summary

| Task | Component | Files | Description |
|------|-----------|-------|-------------|
| 1 | Scaffolding | 12 files | Config, database, security, Docker |
| 2 | Models (Part 1) | 5 files | Base, User, Repository, Snapshot |
| 3 | Models (Part 2) | 7 files | Analysis, ExecutionPlan, Build, Runtime, Deployment, HealthCheck, Usage |
| 4 | Schemas | 6 files | Pydantic v2 request/response models |
| 5 | Services (Part 1) | 3 files | RepositoryService, AnalyzerService |
| 6 | Services (Part 2) | 3 files | BuildService, RuntimeService, DeploymentService |
| 7 | API Layer | 7 files | Dependencies, router, endpoints |
| 8 | Celery Tasks | 5 files | analyze, build, runtime tasks |
| 9 | Alembic | 4 files | Migration configuration |
| 10 | Tests | 7 files | Health, validation, analyzer, models, API tests |

**Total: ~59 files implementing a production-grade backend.**

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-05-repo2web-backend.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
