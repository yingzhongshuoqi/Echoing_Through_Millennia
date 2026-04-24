from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from ..auth.models import AuthUser
from .runtime import AppRuntime


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
