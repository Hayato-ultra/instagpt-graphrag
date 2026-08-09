"""SQLAlchemy engine and session management for PostgreSQL."""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from src.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def get_engine(url: str = None):
    """Create async engine."""
    db_url = url or settings.DATABASE_URL
    return create_async_engine(
        db_url,
        echo=settings.APP_ENV == "development",
        pool_size=5,
        max_overflow=10,
    )


# Module-level engine and session factory
_engine = None
_session_factory = None


def _init_engine():
    global _engine, _session_factory
    if _engine is None:
        _engine = get_engine()
        _session_factory = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )


async def get_async_session():
    """Get an async database session."""
    _init_engine()
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables."""
    _init_engine()
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database engine."""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
