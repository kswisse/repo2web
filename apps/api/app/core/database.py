from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    pass


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

_sync_engine = None
_SyncSessionLocal = None


def _get_sync_session_factory():
    global _sync_engine, _SyncSessionLocal
    if _sync_engine is None:
        from sqlalchemy import create_engine as _create_engine
        from sqlalchemy.orm import sessionmaker as _sessionmaker

        _sync_engine = _create_engine(
            settings.DATABASE_URL.replace("+asyncpg", "+psycopg2"),
            echo=settings.DEBUG,
            pool_size=5,
            max_overflow=5,
            pool_pre_ping=True,
        )
        _SyncSessionLocal = _sessionmaker(bind=_sync_engine)
    return _SyncSessionLocal


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
    factory = _get_sync_session_factory()
    return factory()
