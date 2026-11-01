"""Async engine and session. Compatible with PgBouncer transaction mode."""
import uuid
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


def _engine(url: str):  # type: ignore[no-untyped-def]
    return create_async_engine(
        url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        connect_args={
            # PgBouncer in transaction mode cannot keep named prepared statements.
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
        },
    )


engine = _engine(settings.database_url)
replica_engine = _engine(settings.database_replica_url) if settings.database_replica_url else engine
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
ReadSessionLocal = async_sessionmaker(replica_engine, expire_on_commit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def get_read_session() -> AsyncIterator[AsyncSession]:
    """Replica session for read only hot paths. Falls back to the primary."""
    async with ReadSessionLocal() as session:
        yield session
