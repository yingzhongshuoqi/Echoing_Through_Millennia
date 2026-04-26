from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from ..auth.models import AuthUser
from .runtime import AppRuntime
from .services.user_scope import UserAppScope, build_user_app_scope
from .services.web_console import WebConsoleService


def get_app_runtime(request: Request) -> AppRuntime:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise HTTPException(status_code=503, detail="EchoBot runtime is not ready")
    return runtime


def get_auth_service(runtime=Depends(get_app_runtime)):
    """获取已经初始化完成的认证服务。"""

    auth_service = getattr(runtime, "auth_service", None)
    if auth_service is None or not auth_service.ready:
        raise HTTPException(status_code=503, detail="认证服务未就绪")
    return auth_service


async def get_current_user(
    request: Request,
    auth_service=Depends(get_auth_service),
) -> AuthUser:
    """解析当前请求中的登录用户，没有登录则返回 401。"""

    session_token = request.cookies.get(auth_service.cookie_name, "").strip()
    if not session_token:
        raise HTTPException(status_code=401, detail="请先登录")

    current_user = await auth_service.get_user_by_token(session_token)
    if current_user is None:
        raise HTTPException(status_code=401, detail="登录状态已失效，请重新登录")
    return current_user


async def get_optional_current_user(
    request: Request,
    runtime=Depends(get_app_runtime),
) -> AuthUser | None:
    """在不强制报错的情况下读取当前登录用户。"""

    auth_service = getattr(runtime, "auth_service", None)
    if auth_service is None or not auth_service.ready:
        return None

    session_token = request.cookies.get(auth_service.cookie_name, "").strip()
    if not session_token:
        return None
    return await auth_service.get_user_by_token(session_token)


def get_user_scope(
    current_user=Depends(get_current_user),
    runtime=Depends(get_app_runtime),
) -> UserAppScope:
    """为当前登录用户构建一组最小可用的隔离服务。"""

    if (
        runtime.context is None
        or runtime.tts_service is None
        or runtime.asr_service is None
    ):
        raise HTTPException(status_code=503, detail="EchoBot runtime is not ready")

    user_storage_root = (
        runtime.context.workspace
        / ".echobot"
        / "users"
        / f"user-{current_user.id}"
        / "web_console"
    )
    user_web_console_service = WebConsoleService(
        runtime.context.workspace,
        runtime.tts_service,
        runtime.asr_service,
        storage_root=user_storage_root,
    )
    return build_user_app_scope(
        user=current_user,
        workspace=runtime.context.workspace,
        session_store=runtime.context.session_store,
        agent_session_store=runtime.context.agent_session_store,
        coordinator=runtime.context.coordinator,
        web_console_service=user_web_console_service,
    )
