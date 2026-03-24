from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..agent import AgentCore
from ..config import configure_runtime_logging, load_env_file
from ..memory import ReMeLightSettings, ReMeLightSupport
from ..orchestration import (
    ConversationCoordinator,
    DecisionEngine,
    RoleCardRegistry,
    RoleplayEngine,
)
from ..orchestration.coordinator import RelicContextHook, RelicContextResult
from ..providers.openai_compatible import (
    OpenAICompatibleProvider,
    OpenAICompatibleSettings,
)
from ..runtime.session_runner import SessionAgentRunner
from ..runtime.agent_traces import AgentTraceStore
from ..runtime.settings import RuntimeSettingsStore
from ..runtime.sessions import ChatSession, SessionStore
from ..runtime.system_prompt import build_default_system_prompt
from ..scheduling.cron import CronService
from ..scheduling.heartbeat import HeartbeatService
from ..skill_support import SkillRegistry
from ..tools import ToolRegistry, create_basic_tool_registry


ToolRegistryFactory = Callable[[str, bool], ToolRegistry | None]


@dataclass(slots=True)
class RuntimeOptions:
    env_file: str = ".env"
    workspace: Path | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    delegated_ack_enabled: bool | None = None
    no_tools: bool = False
    no_skills: bool = False
    no_memory: bool = False
    no_heartbeat: bool = False
    heartbeat_interval: int | None = None
    session: str | None = None
    new_session: str | None = None


@dataclass(slots=True)
class RuntimeContext:
    workspace: Path
    agent: AgentCore
    session_store: SessionStore
    agent_session_store: SessionStore
    session: ChatSession | None
    tool_registry: ToolRegistry | None
    skill_registry: SkillRegistry | None
    cron_service: CronService
    heartbeat_service: HeartbeatService | None
    session_runner: SessionAgentRunner
    coordinator: ConversationCoordinator
    role_registry: RoleCardRegistry
    memory_support: ReMeLightSupport | None
    heartbeat_file_path: Path
    heartbeat_interval_seconds: int
    tool_registry_factory: ToolRegistryFactory
    relic_db_engine: object | None = None


def build_runtime_context(
    options: RuntimeOptions,
    *,
    load_session_state: bool,
) -> RuntimeContext:
    workspace = (options.workspace or Path(".")).resolve()
    settings_store = RuntimeSettingsStore(_runtime_settings_path(workspace))
    runtime_settings = settings_store.load()
    env_file_path = _resolve_runtime_path(workspace, options.env_file)
    load_env_file(str(env_file_path))
    configure_runtime_logging()
    lightweight_max_tokens = _env_int("ECHOBOT_LIGHTWEIGHT_MAX_TOKENS", 4096)
    agent_max_steps = _env_int("ECHOBOT_AGENT_MAX_STEPS", 50)
    settings = OpenAICompatibleSettings.from_env()
    decider_provider = _build_provider_from_env(
        prefix="DECIDER_LLM_",
        fallback_settings=settings,
    )
    role_provider = _build_provider_from_env(
        prefix="ROLE_LLM_",
        fallback_settings=settings,
    )

    memory_support = None
    if not options.no_memory and ReMeLightSupport.is_available():
        memory_settings = ReMeLightSettings.from_provider_settings(
            workspace,
            settings,
        )
        memory_support = ReMeLightSupport(memory_settings)

    provider = OpenAICompatibleProvider(settings)
    cron_store_path = workspace / ".echobot" / "cron" / "jobs.json"
    heartbeat_file_path = _heartbeat_file_path(workspace)
    heartbeat_interval_seconds = _heartbeat_interval_seconds(options)
    agent = AgentCore(
        provider,
        system_prompt=build_default_system_prompt(
            workspace,
            enable_project_memory=memory_support is not None,
            memory_workspace=(
                memory_support.working_dir
                if memory_support is not None
                else None
            ),
            enable_scheduling=True,
            cron_store_path=cron_store_path,
            heartbeat_file_path=heartbeat_file_path,
            heartbeat_interval_seconds=heartbeat_interval_seconds,
        ),
        memory_support=memory_support,
    )
    session_store = SessionStore(workspace / ".echobot" / "sessions")
    agent_session_store = SessionStore(workspace / ".echobot" / "agent_sessions")
    agent_trace_store = AgentTraceStore(workspace / ".echobot" / "agent_traces")
    session = _load_session(session_store, options) if load_session_state else None
    cron_service = CronService(cron_store_path)
    tool_registry_factory = _build_tool_registry_factory(
        options,
        workspace=workspace,
        memory_support=memory_support,
        cron_service=cron_service,
    )
    tool_registry = None
    if session is not None:
        tool_registry = tool_registry_factory(session.name, False)
    skill_registry = None if options.no_skills else SkillRegistry.discover()
    session_runner = SessionAgentRunner(
        agent,
        agent_session_store,
        skill_registry=skill_registry,
        tool_registry_factory=tool_registry_factory,
        default_temperature=options.temperature,
        default_max_tokens=options.max_tokens,
        default_max_steps=agent_max_steps,
        trace_store=agent_trace_store,
    )
    role_registry = RoleCardRegistry.discover(project_root=workspace)
    decision_engine = DecisionEngine(
        AgentCore(decider_provider),
        max_tokens=lightweight_max_tokens,
    )
    roleplay_engine = RoleplayEngine(
        AgentCore(role_provider),
        role_registry,
        default_temperature=options.temperature,
        default_max_tokens=options.max_tokens,
        lightweight_max_tokens=lightweight_max_tokens,
    )
    relic_hook, relic_db_engine = _build_relic_context_hook(provider)

    coordinator = ConversationCoordinator(
        session_store=session_store,
        agent_runner=session_runner,
        decision_engine=decision_engine,
        roleplay_engine=roleplay_engine,
        role_registry=role_registry,
        delegated_ack_enabled=_delegated_ack_enabled(
            options,
            runtime_settings=runtime_settings,
        ),
        relic_context_hook=relic_hook,
    )
    heartbeat_service = None
    if not options.no_heartbeat and _heartbeat_enabled():
        heartbeat_service = HeartbeatService(
            heartbeat_file=heartbeat_file_path,
            provider=provider,
            interval_seconds=heartbeat_interval_seconds,
            enabled=True,
        )

    return RuntimeContext(
        workspace=workspace,
        agent=agent,
        session_store=session_store,
        agent_session_store=agent_session_store,
        session=session,
        tool_registry=tool_registry,
        skill_registry=skill_registry,
        cron_service=cron_service,
        heartbeat_service=heartbeat_service,
        session_runner=session_runner,
        coordinator=coordinator,
        role_registry=role_registry,
        memory_support=memory_support,
        heartbeat_file_path=heartbeat_file_path,
        heartbeat_interval_seconds=heartbeat_interval_seconds,
        tool_registry_factory=tool_registry_factory,
        relic_db_engine=relic_db_engine,
    )


def _build_tool_registry_factory(
    options: RuntimeOptions,
    *,
    workspace: Path,
    memory_support: ReMeLightSupport | None,
    cron_service: CronService,
) -> ToolRegistryFactory:
    def factory(session_name: str, scheduled_context: bool) -> ToolRegistry | None:
        if options.no_tools:
            return None
        return create_basic_tool_registry(
            workspace,
            memory_support=memory_support,
            cron_service=cron_service,
            session_name=session_name,
            allow_cron_mutations=not scheduled_context,
        )

    return factory


def _load_session(
    session_store: SessionStore,
    options: RuntimeOptions,
) -> ChatSession:
    if options.new_session:
        return session_store.create_session(options.new_session)

    if options.session:
        session = session_store.load_or_create_session(options.session)
        session_store.set_current_session(session.name)
        return session

    return session_store.load_current_session()


def _heartbeat_file_path(workspace: Path) -> Path:
    file_name = os.environ.get(
        "ECHOBOT_HEARTBEAT_FILE",
        ".echobot/HEARTBEAT.md",
    )
    return workspace / file_name


def _heartbeat_interval_seconds(options: RuntimeOptions) -> int:
    if options.heartbeat_interval is not None:
        return max(int(options.heartbeat_interval), 1)
    raw_value = os.environ.get("ECHOBOT_HEARTBEAT_INTERVAL_SECONDS", "1800")
    try:
        value = int(raw_value)
    except ValueError:
        value = 1800
    return max(value, 1)


def _heartbeat_enabled() -> bool:
    raw_value = os.environ.get("ECHOBOT_HEARTBEAT_ENABLED", "true").strip().lower()
    return raw_value not in {"0", "false", "no", "off"}


def _delegated_ack_enabled(
    options: RuntimeOptions,
    *,
    runtime_settings,
) -> bool:
    if options.delegated_ack_enabled is not None:
        return bool(options.delegated_ack_enabled)
    if runtime_settings.delegated_ack_enabled is not None:
        return bool(runtime_settings.delegated_ack_enabled)
    return _env_bool("ECHOBOT_DELEGATED_ACK_ENABLED", True)


def _env_int(name: str, default: int) -> int:
    raw_value = os.environ.get(name, "").strip()
    if not raw_value:
        return default
    try:
        return max(int(raw_value), 1)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default

    cleaned = raw_value.strip().lower()
    if not cleaned:
        return default
    return cleaned not in {"0", "false", "no", "off"}


def _resolve_runtime_path(workspace: Path, path: str | Path) -> Path:
    resolved_path = Path(path).expanduser()
    if resolved_path.is_absolute():
        return resolved_path
    return workspace / resolved_path


def _runtime_settings_path(workspace: Path) -> Path:
    return workspace / ".echobot" / "runtime_settings.json"


def _build_provider_from_env(
    *,
    prefix: str,
    fallback_settings: OpenAICompatibleSettings,
) -> OpenAICompatibleProvider:
    if _has_provider_env(prefix):
        return OpenAICompatibleProvider(
            OpenAICompatibleSettings.from_env(prefix=prefix),
        )
    return OpenAICompatibleProvider(fallback_settings)


def _has_provider_env(prefix: str) -> bool:
    api_key_name = f"{prefix}API_KEY"
    model_name = f"{prefix}MODEL"
    return bool(os.environ.get(api_key_name, "").strip()) and bool(
        os.environ.get(model_name, "").strip()
    )


def _build_relic_context_hook(
    provider: OpenAICompatibleProvider,
) -> tuple[RelicContextHook | None, object | None]:
    """Build a relic context hook if RELIC_DATABASE_URL is configured."""
    import logging as _logging

    _logger = _logging.getLogger(__name__)

    relic_db_url = os.environ.get("RELIC_DATABASE_URL", "").strip()
    if not relic_db_url:
        _logger.info("RELIC_DATABASE_URL not set — relic knowledge features disabled")
        return None, None

    embedding_api_key = os.environ.get("EMBEDDING_API_KEY", "").strip()
    embedding_model = os.environ.get("EMBEDDING_MODEL", "text-embedding-v3").strip()
    embedding_base_url = os.environ.get(
        "EMBEDDING_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ).strip()
    embedding_dimensions = int(os.environ.get("EMBEDDING_DIMENSIONS", "1024"))

    if not embedding_api_key:
        _logger.warning("EMBEDDING_API_KEY not set — relic knowledge features disabled")
        return None, None

    from ..relic_knowledge.db import init_relic_db, get_relic_db_session
    from ..relic_knowledge.embeddings import EmbeddingService
    from ..relic_knowledge.emotion_analyzer import EmotionAnalyzer
    from ..relic_knowledge.retriever import RelicRetriever
    from ..relic_knowledge.relic_matcher import RelicMatcher
    from ..relic_knowledge.guided_dialogue import get_phase_instruction, get_style_instruction
    from ..models import LLMMessage

    embedding_service = EmbeddingService(
        api_key=embedding_api_key,
        base_url=embedding_base_url,
        model=embedding_model,
        dimensions=embedding_dimensions,
    )
    emotion_analyzer = EmotionAnalyzer(provider)
    retriever = RelicRetriever(embedding_service)
    matcher = RelicMatcher(retriever)

    _turn_counters: dict[str, int] = {}

    async def relic_context_hook(
        session_name: str,
        prompt: str,
        history: list[LLMMessage],
    ) -> RelicContextResult | None:
        from ..relic_knowledge import db as _relic_db_mod

        if _relic_db_mod._engine is None:
            return None

        turn_count = _turn_counters.get(session_name, 0)
        _turn_counters[session_name] = turn_count + 1

        emotion = await emotion_analyzer.analyze(
            prompt, history, turn_count, session_key=session_name,
        )

        async with get_relic_db_session() as db:
            match = await matcher.match(db, emotion)

        # --- 构建 Plutchik 情感上下文 ---
        dominant_str = "、".join(
            f"{d['cn']}({d.get('intensity_name_cn', d['cn'])})"
            for d in emotion.dominant_emotions[:3]
        ) or "平静"
        dyad_str = "、".join(
            d["name_cn"] for d in emotion.active_dyads[:2]
        ) if emotion.active_dyads else "无"
        tension_str = "、".join(
            f"{t['pair'][0]}↔{t['pair'][1]}"
            for t in emotion.opposite_tensions[:1]
        ) if emotion.opposite_tensions else "无"
        emotion_summary = (
            f"用户情感分析（Plutchik模型）：\n"
            f"  主导情绪：{dominant_str}\n"
            f"  复合情绪：{dyad_str}\n"
            f"  情感强度：{emotion.intensity_level.value}（{emotion.intensity}/10）\n"
            f"  情感矛盾：{tension_str}"
        )

        phase_instruction = get_phase_instruction(emotion.phase, emotion)
        style_instruction = get_style_instruction("classical")

        if match is None:
            context = (
                f"\n\n--- 千岁回响·情感疗愈上下文 ---\n"
                f"{emotion_summary}\n"
                f"当前未匹配到文物。请根据角色卡进行回复。\n"
                f"{phase_instruction}\n"
                f"{style_instruction}"
            )
            return RelicContextResult(
                extra_system_context=context,
                emotion_data=emotion.to_dict(),
                relic_data=None,
            )

        relic = match.relic
        context = (
            f"\n\n--- 千岁回响·情感疗愈上下文 ---\n"
            f"{emotion_summary}\n"
            f"匹配文物：{relic.name}（{relic.dynasty}）\n"
            f"文物故事：{relic.story[:500]}\n"
            f"人生启示：{relic.life_insight or '（无）'}\n"
            f"匹配度：{match.score:.2f}\n"
            f"\n{phase_instruction}\n"
            f"{style_instruction}\n"
            f"\n请将上述文物故事自然融入你的回复中，帮助用户从中获得疗愈和启发。"
        )
        return RelicContextResult(
            extra_system_context=context,
            emotion_data=emotion.to_dict(),
            relic_data=match.to_dict(),
        )

    _logger.info("Relic knowledge hook enabled (DB: %s)", relic_db_url.split("@")[-1])
    return relic_context_hook, "relic_db_configured"
