from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ...auth.models import AuthUser
from ...orchestration.coordinator import ConversationCoordinator
from ...orchestration.jobs import ConversationJob, OrchestratedTurnResult
from ...orchestration.route_modes import RouteMode
from ...runtime.sessions import ChatSession, SessionInfo, SessionStore, normalize_session_name
from .web_console import WebConsoleService


@dataclass(slots=True)
class UserAppScope:
    """聚合当前登录用户可见的最小运行时能力。"""

    user: AuthUser
    session_service: "UserScopedSessionService"
    chat_service: "UserScopedChatService"
    web_console_service: WebConsoleService


class UserScopedSessionService:
    """在不重构底层会话架构的前提下，为登录用户提供最小会话隔离。"""

    def __init__(
        self,
        *,
        user: AuthUser,
        workspace: Path,
        session_store: SessionStore,
        agent_session_store: SessionStore | None,
        coordinator: ConversationCoordinator,
    ) -> None:
        self._user = user
        self._workspace = Path(workspace)
        self._session_store = session_store
        self._agent_session_store = agent_session_store
        self._coordinator = coordinator
        # 这里单独记录当前用户的“当前会话”，避免多个账号共用全局 index。
        self._user_state_store = SessionStore(self._user_root / "session_state")

    @property
    def user_storage_root(self) -> Path:
        return self._user_root

    def to_internal_name(self, public_name: str) -> str:
        """把前端可见的会话名映射为内部存储名。"""

        return f"{self._session_prefix}{normalize_session_name(public_name)}"

    def to_public_name(self, internal_name: str) -> str:
        """把内部会话名还原为当前用户可见的会话名。"""

        public_name = self.public_name_or_none(internal_name)
        if public_name is None:
            raise ValueError(f"Session does not belong to user {self._user.id}: {internal_name}")
        return public_name

    def owns_internal_session(self, internal_name: str) -> bool:
        return self.public_name_or_none(internal_name) is not None

    def public_name_or_none(self, internal_name: str) -> str | None:
        cleaned = str(internal_name or "").strip()
        if not cleaned.startswith(self._session_prefix):
            return None
        public_name = cleaned[len(self._session_prefix):]
        if not public_name:
            return None
        return public_name

    async def list_sessions(self) -> list[SessionInfo]:
        """只返回当前登录用户自己的会话列表。"""

        session_infos = await asyncio.to_thread(self._session_store.list_sessions)
        filtered: list[SessionInfo] = []
        for item in session_infos:
            public_name = self.public_name_or_none(item.name)
            if public_name is None:
                continue
            filtered.append(
                SessionInfo(
                    name=public_name,
                    message_count=item.message_count,
                    updated_at=item.updated_at,
                )
            )
        return filtered

    async def load_session(self, name: str) -> ChatSession:
        internal_name = self.to_internal_name(name)
        session = await asyncio.to_thread(self._session_store.load_session, internal_name)
        return self._publicize_session(session)

    async def load_or_create_session(self, name: str) -> ChatSession:
        internal_name = self.to_internal_name(name)
        session = await asyncio.to_thread(self._session_store.load_or_create_session, internal_name)
        await self._coordinator.restore_session(session.name)
        await self.set_current_session_internal(session.name)
        return self._publicize_session(session)

    async def load_current_session(self) -> ChatSession:
        current_internal_name = await asyncio.to_thread(
            self._user_state_store.get_current_session_name,
        )
        if current_internal_name and self.owns_internal_session(current_internal_name):
            if await asyncio.to_thread(self._session_store.has_session, current_internal_name):
                session = await asyncio.to_thread(
                    self._session_store.load_session,
                    current_internal_name,
                )
                return self._publicize_session(session)

        session_infos = await self.list_sessions()
        if session_infos:
            session = await self.load_session(session_infos[0].name)
            await self.set_current_session(session.name)
            return session

        return await self.create_session("default")

    async def create_session(self, name: str | None = None) -> ChatSession:
        public_name = normalize_session_name(name) if name else await asyncio.to_thread(
            self._generate_public_session_name,
        )
        internal_name = self.to_internal_name(public_name)
        if await asyncio.to_thread(self._session_store.has_session, internal_name):
            raise ValueError(f"Session already exists: {public_name}")

        session = ChatSession(
            name=internal_name,
            history=[],
            updated_at="",
            compressed_summary="",
        )
        await asyncio.to_thread(self._session_store.save_session, session)
        await self._coordinator.restore_session(session.name)
        await self.set_current_session_internal(session.name)
        return self._publicize_session(session)

    async def set_current_session(self, name: str) -> None:
        await self.set_current_session_internal(self.to_internal_name(name))

    async def set_current_session_internal(self, internal_name: str) -> None:
        if not self.owns_internal_session(internal_name):
            raise ValueError(f"Session does not belong to user {self._user.id}: {internal_name}")
        await asyncio.to_thread(
            self._user_state_store.set_current_session,
            internal_name,
        )

    async def switch_session(self, name: str) -> ChatSession:
        session = await self.load_session(name)
        await self.set_current_session(session.name)
        await self._coordinator.restore_session(self.to_internal_name(session.name))
        return session

    async def rename_session(self, old_name: str, new_name: str) -> ChatSession:
        normalized_old_name = normalize_session_name(old_name)
        normalized_new_name = normalize_session_name(new_name)
        if normalized_old_name == normalized_new_name:
            return await self.load_session(normalized_old_name)

        old_internal_name = self.to_internal_name(normalized_old_name)
        new_internal_name = self.to_internal_name(normalized_new_name)
        if await asyncio.to_thread(self._session_store.has_session, new_internal_name):
            raise ValueError(f"Session already exists: {normalized_new_name}")

        await self._coordinator.cancel_jobs_for_session(old_internal_name)
        session = await asyncio.to_thread(
            self._session_store.rename_session,
            old_internal_name,
            new_internal_name,
        )
        if self._agent_session_store is not None:
            try:
                await asyncio.to_thread(
                    self._agent_session_store.rename_session,
                    old_internal_name,
                    new_internal_name,
                )
            except ValueError:
                pass

        current_internal_name = await asyncio.to_thread(
            self._user_state_store.get_current_session_name,
        )
        if current_internal_name == old_internal_name:
            await self.set_current_session_internal(new_internal_name)
        await self._coordinator.restore_session(session.name)
        return self._publicize_session(session)

    async def delete_session(self, name: str) -> bool:
        internal_name = self.to_internal_name(name)
        if not await asyncio.to_thread(self._session_store.has_session, internal_name):
            return False
        await self.purge_session(name)
        return True

    async def purge_session(self, name: str) -> None:
        await self._purge_internal_session(self.to_internal_name(name))

    async def _purge_internal_session(self, internal_name: str) -> None:
        await self._coordinator.mark_session_deleted(internal_name)
        await self._coordinator.cancel_jobs_for_session(internal_name)
        await asyncio.to_thread(self._session_store.delete_session, internal_name)
        if self._agent_session_store is not None:
            await asyncio.to_thread(self._agent_session_store.delete_session, internal_name)

        current_internal_name = await asyncio.to_thread(
            self._user_state_store.get_current_session_name,
        )
        if current_internal_name != internal_name:
            return

        remaining_sessions = await self.list_sessions()
        if remaining_sessions:
            await self.set_current_session(remaining_sessions[0].name)
            return

        await self.create_session("default")

    def _publicize_session(self, session: ChatSession) -> ChatSession:
        return ChatSession(
            name=self.to_public_name(session.name),
            history=list(session.history),
            updated_at=session.updated_at,
            compressed_summary=session.compressed_summary,
            metadata=dict(session.metadata),
        )

    def _publicize_job(self, job: ConversationJob) -> ConversationJob:
        return ConversationJob(
            job_id=job.job_id,
            session_name=self.to_public_name(job.session_name),
            prompt=job.prompt,
            immediate_response=job.immediate_response,
            role_name=job.role_name,
            status=job.status,
            created_at=job.created_at,
            updated_at=job.updated_at,
            trace_run_id=job.trace_run_id,
            final_response=job.final_response,
            error=job.error,
            steps=job.steps,
        )

    def publicize_turn_result(self, result: OrchestratedTurnResult) -> OrchestratedTurnResult:
        return OrchestratedTurnResult(
            session=self._publicize_session(result.session),
            response_text=result.response_text,
            delegated=result.delegated,
            completed=result.completed,
            job_id=result.job_id,
            status=result.status,
            role_name=result.role_name,
            steps=result.steps,
            compressed_summary=result.compressed_summary,
            relic_context=result.relic_context,
        )

    def publicize_job(self, job: ConversationJob | None) -> ConversationJob | None:
        if job is None:
            return None
        if not self.owns_internal_session(job.session_name):
            return None
        return self._publicize_job(job)

    def _generate_public_session_name(self) -> str:
        prefix = datetime.now().strftime("session-%Y%m%d-%H%M%S")
        candidate = prefix
        counter = 1
        while self._session_store.has_session(self.to_internal_name(candidate)):
            counter += 1
            candidate = f"{prefix}-{counter}"
        return candidate

    @property
    def _session_prefix(self) -> str:
        return f"u{self._user.id}__"

    @property
    def _user_root(self) -> Path:
        return self._workspace / ".echobot" / "users" / f"user-{self._user.id}"


class UserScopedChatService:
    """为登录用户包装聊天能力，统一做会话名映射和归属校验。"""

    def __init__(
        self,
        *,
        coordinator: ConversationCoordinator,
        session_service: UserScopedSessionService,
    ) -> None:
        self._coordinator = coordinator
        self._session_service = session_service

    async def run_prompt(
        self,
        session_name: str,
        prompt: str,
        *,
        image_urls: list[str] | None = None,
        role_name: str | None = None,
        route_mode: RouteMode | None = None,
    ) -> OrchestratedTurnResult:
        internal_name = self._session_service.to_internal_name(session_name)
        result = await self._coordinator.handle_user_turn(
            internal_name,
            prompt,
            image_urls=image_urls,
            role_name=role_name,
            route_mode=route_mode,
        )
        await self._session_service.set_current_session_internal(result.session.name)
        return self._session_service.publicize_turn_result(result)

    async def run_prompt_stream(
        self,
        session_name: str,
        prompt: str,
        *,
        image_urls: list[str] | None = None,
        role_name: str | None = None,
        route_mode: RouteMode | None = None,
        on_chunk=None,
    ) -> OrchestratedTurnResult:
        internal_name = self._session_service.to_internal_name(session_name)
        result = await self._coordinator.handle_user_turn_stream(
            internal_name,
            prompt,
            image_urls=image_urls,
            role_name=role_name,
            route_mode=route_mode,
            on_chunk=on_chunk,
        )
        await self._session_service.set_current_session_internal(result.session.name)
        return self._session_service.publicize_turn_result(result)

    async def set_role(
        self,
        session_name: str,
        role_name: str,
    ) -> ChatSession:
        internal_name = self._session_service.to_internal_name(session_name)
        session = await self._coordinator.set_session_role(internal_name, role_name)
        await self._session_service.set_current_session_internal(session.name)
        return self._session_service._publicize_session(session)

    async def current_role_name(self, session_name: str) -> str:
        internal_name = self._session_service.to_internal_name(session_name)
        return await self._coordinator.current_role_name(internal_name)

    async def set_route_mode(
        self,
        session_name: str,
        route_mode: RouteMode,
    ) -> ChatSession:
        internal_name = self._session_service.to_internal_name(session_name)
        session = await self._coordinator.set_session_route_mode(internal_name, route_mode)
        await self._session_service.set_current_session_internal(session.name)
        return self._session_service._publicize_session(session)

    async def current_route_mode(self, session_name: str) -> RouteMode:
        internal_name = self._session_service.to_internal_name(session_name)
        return await self._coordinator.current_route_mode(internal_name)

    def available_roles(self) -> list[str]:
        return self._coordinator.available_roles()

    async def get_job(self, job_id: str) -> ConversationJob | None:
        job = await self._coordinator.get_job(job_id)
        return self._session_service.publicize_job(job)

    async def get_job_trace(
        self,
        job_id: str,
    ) -> tuple[ConversationJob | None, list[dict[str, object]]]:
        job, events = await self._coordinator.get_job_trace(job_id)
        public_job = self._session_service.publicize_job(job)
        if public_job is None:
            return None, []
        return public_job, events

    async def cancel_job(self, job_id: str) -> ConversationJob | None:
        current_job = await self._coordinator.get_job(job_id)
        if self._session_service.publicize_job(current_job) is None:
            return None
        job = await self._coordinator.cancel_job(job_id)
        return self._session_service.publicize_job(job)


def build_user_app_scope(
    *,
    user: AuthUser,
    workspace: Path,
    session_store: SessionStore,
    agent_session_store: SessionStore | None,
    coordinator: ConversationCoordinator,
    web_console_service: WebConsoleService,
) -> UserAppScope:
    """统一构建当前请求的用户作用域对象。"""

    session_service = UserScopedSessionService(
        user=user,
        workspace=workspace,
        session_store=session_store,
        agent_session_store=agent_session_store,
        coordinator=coordinator,
    )
    chat_service = UserScopedChatService(
        coordinator=coordinator,
        session_service=session_service,
    )
    return UserAppScope(
        user=user,
        session_service=session_service,
        chat_service=chat_service,
        web_console_service=web_console_service,
    )
