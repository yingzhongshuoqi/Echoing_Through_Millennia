from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta

from fastapi import Response
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from ...auth.db import close_auth_db, get_auth_db_session, init_auth_db
from ...auth.models import AuthSession, AuthUser
from ...auth.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    normalize_username,
    utc_now,
    validate_password,
    verify_password,
)


@dataclass(slots=True)
class AuthCookieConfig:
    """登录 Cookie 配置。"""

    name: str
    max_age_seconds: int
    secure: bool
    samesite: str


class AuthService:
    """管理用户注册、登录和服务端会话。"""

    def __init__(self) -> None:
        self.cookie_config = _load_cookie_config()
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def cookie_name(self) -> str:
        return self.cookie_config.name

    async def startup(self) -> None:
        """在应用启动时初始化认证数据库。"""

        engine = await init_auth_db()
        self._ready = engine is not None

    async def shutdown(self) -> None:
        """在应用停止时释放认证数据库连接。"""

        await close_auth_db()
        self._ready = False

    async def register_user(self, username: str, password: str) -> tuple[AuthUser, str]:
        """创建新用户，并直接签发一个登录会话。"""

        self._ensure_ready()
        display_name, username_key = normalize_username(username)
        normalized_password = validate_password(password)

        async with get_auth_db_session() as db:
            await self._delete_expired_sessions(db)
            existing = await db.scalar(
                select(AuthUser).where(AuthUser.username_key == username_key),
            )
            if existing is not None:
                raise ValueError("用户名已存在")

            user = AuthUser(
                username=display_name,
                username_key=username_key,
                password_hash=hash_password(normalized_password),
            )
            db.add(user)
            await db.flush()
            await db.refresh(user)

            session_token = await self._create_session(db, user.id)
            return user, session_token

    async def login_user(self, username: str, password: str) -> tuple[AuthUser, str]:
        """校验账号密码并签发新的登录会话。"""

        self._ensure_ready()
        _, username_key = normalize_username(username)
        normalized_password = validate_password(password)

        async with get_auth_db_session() as db:
            await self._delete_expired_sessions(db)
            user = await db.scalar(
                select(AuthUser).where(AuthUser.username_key == username_key),
            )
            if user is None or not verify_password(normalized_password, user.password_hash):
                raise PermissionError("用户名或密码错误")

            session_token = await self._create_session(db, user.id)
            await db.refresh(user)
            return user, session_token

    async def logout(self, token: str | None) -> None:
        """删除当前浏览器对应的服务端会话。"""

        if not self._ready or not token:
            return

        async with get_auth_db_session() as db:
            await db.execute(
                delete(AuthSession).where(
                    AuthSession.token_hash == hash_session_token(token),
                )
            )

    async def get_user_by_token(self, token: str | None) -> AuthUser | None:
        """通过 Cookie 令牌解析当前登录用户。"""

        self._ensure_ready()
        if not token:
            return None

        now = utc_now()
        async with get_auth_db_session() as db:
            await self._delete_expired_sessions(db, now=now)
            result = await db.execute(
                select(AuthSession)
                .options(selectinload(AuthSession.user))
                .where(AuthSession.token_hash == hash_session_token(token)),
            )
            auth_session = result.scalar_one_or_none()
            if auth_session is None or auth_session.expires_at <= now:
                return None

            auth_session.last_used_at = now
            return auth_session.user

    def set_login_cookie(self, response: Response, token: str) -> None:
        """向浏览器写入 HttpOnly 登录 Cookie。"""

        response.set_cookie(
            key=self.cookie_config.name,
            value=token,
            httponly=True,
            max_age=self.cookie_config.max_age_seconds,
            path="/",
            samesite=self.cookie_config.samesite,
            secure=self.cookie_config.secure,
        )

    def clear_login_cookie(self, response: Response) -> None:
        """清除浏览器中的登录 Cookie。"""

        response.delete_cookie(
            key=self.cookie_config.name,
            path="/",
            httponly=True,
            samesite=self.cookie_config.samesite,
            secure=self.cookie_config.secure,
        )

    async def _create_session(self, db, user_id: int) -> str:
        """创建新的服务端会话记录，并返回原始令牌。"""

        now = utc_now()
        token = generate_session_token()
        db.add(
            AuthSession(
                user_id=user_id,
                token_hash=hash_session_token(token),
                last_used_at=now,
                expires_at=now + timedelta(seconds=self.cookie_config.max_age_seconds),
            )
        )
        await db.flush()
        return token

    async def _delete_expired_sessions(self, db, *, now=None) -> None:
        """顺手清理已过期会话，避免表无限增长。"""

        current_time = now or utc_now()
        await db.execute(
            delete(AuthSession).where(AuthSession.expires_at <= current_time),
        )

    def _ensure_ready(self) -> None:
        """在依赖认证服务前确认数据库已完成初始化。"""

        if not self._ready:
            raise RuntimeError("认证数据库未配置，请先设置 AUTH_DATABASE_URL 或 RELIC_DATABASE_URL")


def _load_cookie_config() -> AuthCookieConfig:
    """从环境变量读取登录 Cookie 配置。"""

    secure = os.environ.get("AUTH_COOKIE_SECURE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    samesite = os.environ.get("AUTH_COOKIE_SAMESITE", "lax").strip().lower() or "lax"
    max_age_seconds = int(
        os.environ.get("AUTH_SESSION_MAX_AGE_SECONDS", str(7 * 24 * 60 * 60)),
    )
    return AuthCookieConfig(
        name=os.environ.get("AUTH_COOKIE_NAME", "echobot_session").strip() or "echobot_session",
        max_age_seconds=max_age_seconds,
        secure=secure,
        samesite=samesite,
    )
