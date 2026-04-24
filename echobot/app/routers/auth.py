from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from ..schemas import (
    AuthUserModel,
    LoginRequest,
    LogoutResponse,
    RegisterRequest,
    auth_user_model_from_entity,
)
from ..state import get_app_runtime, get_current_user


router = APIRouter(tags=["auth"])


@router.post(
    "/auth/register",
    response_model=AuthUserModel,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    request: RegisterRequest,
    response: Response,
    runtime=Depends(get_app_runtime),
) -> AuthUserModel:
    """注册新用户，并直接建立登录态。"""

    if runtime.auth_service is None:
        raise HTTPException(status_code=503, detail="认证服务未就绪")

    try:
        user, session_token = await runtime.auth_service.register_user(
            request.username,
            request.password,
        )
    except ValueError as exc:
        status_code = 409 if "已存在" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    runtime.auth_service.set_login_cookie(response, session_token)
    return auth_user_model_from_entity(user)


@router.post("/auth/login", response_model=AuthUserModel)
async def login(
    request: LoginRequest,
    response: Response,
    runtime=Depends(get_app_runtime),
) -> AuthUserModel:
    """登录已有用户，并写入新的会话 Cookie。"""

    if runtime.auth_service is None:
        raise HTTPException(status_code=503, detail="认证服务未就绪")

    try:
        user, session_token = await runtime.auth_service.login_user(
            request.username,
            request.password,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    runtime.auth_service.set_login_cookie(response, session_token)
    return auth_user_model_from_entity(user)


@router.post("/auth/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    response: Response,
    runtime=Depends(get_app_runtime),
) -> LogoutResponse:
    """退出当前登录态，并清除浏览器 Cookie。"""

    if runtime.auth_service is None:
        raise HTTPException(status_code=503, detail="认证服务未就绪")

    session_token = request.cookies.get(runtime.auth_service.cookie_name, "").strip()

    await runtime.auth_service.logout(session_token)
    runtime.auth_service.clear_login_cookie(response)
    return LogoutResponse(logged_out=True)


@router.get("/auth/me", response_model=AuthUserModel)
async def get_current_login_user(current_user=Depends(get_current_user)) -> AuthUserModel:
    """查询当前已登录用户。"""

    return auth_user_model_from_entity(current_user)
