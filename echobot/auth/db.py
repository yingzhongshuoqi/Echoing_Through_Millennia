from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

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


class AuthBase(DeclarativeBase):
    """认证表的声明式基类。"""


async def init_auth_db(database_url: str | None = None) -> AsyncEngine | None:
    """初始化认证数据库连接，未配置时返回 None。"""

    global _engine, _session_factory

    if _engine is not None and _session_factory is not None:
        return _engine

    url = database_url or _resolve_auth_database_url()
    if not url:
        logger.info("AUTH_DATABASE_URL not set and RELIC_DATABASE_URL unavailable")
        return None

    _engine = create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    from .models import AuthSession, AuthUser  # noqa: F401

    async with _engine.begin() as conn:
        await conn.run_sync(AuthBase.metadata.create_all)

    logger.info("Authentication database connected: %s", url.split("@")[-1])
    return _engine


async def close_auth_db() -> None:
    """关闭认证数据库连接。"""

    global _engine, _session_factory

    if _engine is None:
        return

    await _engine.dispose()
    _engine = None
    _session_factory = None
    logger.info("Authentication database connection closed")


@asynccontextmanager
async def get_auth_db_session() -> AsyncIterator[AsyncSession]:
    """获取一个带自动提交/回滚的异步数据库会话。"""

    if _session_factory is None:
        raise RuntimeError("Authentication database not initialized")

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def _resolve_auth_database_url() -> str:
    """优先使用认证库连接串，未配置时复用现有 PostgreSQL 配置。"""

    return (
        os.environ.get("AUTH_DATABASE_URL", "").strip()
        or os.environ.get("RELIC_DATABASE_URL", "").strip()
    )
