from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from ..runtime.bootstrap import RuntimeOptions
from .routers import auth, chat, channels, cron, health, heartbeat, relics, roles, sessions, web
from .runtime import ASRServiceBuilder, AppRuntime, RuntimeContextBuilder, TTSServiceBuilder
from .state import get_current_user, get_optional_current_user


WEB_ASSETS_DIR = Path(__file__).with_name("web")


def create_app(
    *,
    runtime_options: RuntimeOptions | None = None,
    channel_config_path: str | Path = ".echobot/channels.json",
    context_builder: RuntimeContextBuilder | None = None,
    tts_service_builder: TTSServiceBuilder | None = None,
    asr_service_builder: ASRServiceBuilder | None = None,
) -> FastAPI:
    options = runtime_options or RuntimeOptions()
    runtime = AppRuntime(
        runtime_options=options,
        channel_config_path=channel_config_path,
        context_builder=context_builder,
        tts_service_builder=tts_service_builder,
        asr_service_builder=asr_service_builder,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await runtime.start()
        app.state.runtime = runtime
        try:
            yield
        finally:
            await runtime.stop()

    app = FastAPI(
        title="EchoBot API",
        description="Runtime API for EchoBot daemon and future web console.",
        lifespan=lifespan,
    )

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "name": "EchoBot API",
            "docs": "/docs",
        }

    @app.get("/web", include_in_schema=False)
    async def web_console(
        request: Request,
        current_user=Depends(get_optional_current_user),
    ):
        # 未登录时先跳转到登录页，登录后再回到当前聊天页。
        if current_user is None:
            next_target = request.url.path
            if request.url.query:
                next_target = f"{next_target}?{request.url.query}"
            return RedirectResponse(
                f"/login?next={quote(next_target, safe='/?=&')}",
                status_code=303,
            )
        return FileResponse(WEB_ASSETS_DIR / "index.html")

    @app.get("/login", include_in_schema=False)
    async def login_page(current_user=Depends(get_optional_current_user)):
        # 已登录时无需重复进入登录页。
        if current_user is not None:
            return RedirectResponse("/web", status_code=303)
        return FileResponse(WEB_ASSETS_DIR / "login.html")

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> FileResponse:
        return FileResponse(
            WEB_ASSETS_DIR / "favicon.svg",
            media_type="image/svg+xml",
        )

    app.mount(
        "/web/assets",
        StaticFiles(directory=WEB_ASSETS_DIR),
        name="web-assets",
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    protected_dependencies = [Depends(get_current_user)]
    app.include_router(
        sessions.router,
        prefix="/api",
        dependencies=protected_dependencies,
    )
    app.include_router(
        chat.router,
        prefix="/api",
        dependencies=protected_dependencies,
    )
    app.include_router(
        cron.router,
        prefix="/api",
        dependencies=protected_dependencies,
    )
    app.include_router(
        heartbeat.router,
        prefix="/api",
        dependencies=protected_dependencies,
    )
    app.include_router(
        roles.router,
        prefix="/api",
        dependencies=protected_dependencies,
    )
    app.include_router(
        channels.router,
        prefix="/api",
        dependencies=protected_dependencies,
    )
    app.include_router(web.router, prefix="/api")
    app.include_router(
        relics.router,
        prefix="/api",
        dependencies=protected_dependencies,
    )
    return app
