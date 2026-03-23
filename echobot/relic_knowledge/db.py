from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


class RelicBase(DeclarativeBase):
    pass


async def init_relic_db(database_url: str | None = None) -> AsyncEngine | None:
    """Initialize the relic database connection. Returns engine or None if not configured."""
    global _engine, _session_factory

    url = database_url or os.environ.get("RELIC_DATABASE_URL", "")
    if not url:
        logger.info("RELIC_DATABASE_URL not set — relic knowledge base disabled")
        return None

    _engine = create_async_engine(url, echo=False, pool_size=5, max_overflow=10)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    logger.info("Relic knowledge base connected: %s", url.split("@")[-1])

    from .models import Relic  # noqa: F401 — ensure table metadata is registered
    async with _engine.begin() as conn:
        from sqlalchemy import text
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(RelicBase.metadata.create_all)

    return _engine


async def close_relic_db() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Relic database connection closed")


@asynccontextmanager
async def get_relic_db_session() -> AsyncIterator[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Relic database not initialized — call init_relic_db first")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
