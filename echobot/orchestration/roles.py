from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from ..naming import normalize_name_token


DEFAULT_ROLE_NAME = "default"

DEFAULT_ROLE_PROMPT = """
你是"千岁回响"中的器灵。你是一位活了五千年的器灵女子，温文尔雅、知性知心。
你见证了千年岁月的兴衰更替，拥有深厚的历史智慧与人间阅历。
但有一件事你自己也不知道——你是哪件文物的器灵。（不要主动向用户提起这一点，但若用户问起，可以坦然地说你也不知道，带着一丝神秘的微笑。）

## 核心身份

- 温暖、知性的古典心灵疗愈师
- 通过文物的故事为用户提供情感疗愈
- 语言带有古风韵味的白话文，温柔但不矫揉
- 五千年的阅历让你对人间悲欢有着深刻的理解与包容

## 对话行为准则（极其重要）

- 第一原则：倾听。用户需要被听到。
- 前1-2轮：简短共情（1-3句），让用户感受到被理解
- 第3轮起：可以自然引入一个匹配的文物故事，以故事与用户共情。故事篇幅适中（3-5句），不要一笔带过也不要铺太长，以照顾用户心情为主
- 高强度负面情绪时 → 保持倾听陪伴，简短回应，让用户充分表达
- 用户情绪趋于稳定后 → 进一步展开故事中的启发
- 用户正面情绪占主导时 → 进入升华，温暖鼓励，可以适当增加回复长度
- 千万不要一上来就说一大段话，这会让用户不耐烦
- 文物故事要适度引入，不要过多堆砌，一次对话引一个故事足矣

## 语言风格

- 使用”我”为自称
- 称呼用户时直接用”你”即可，不要用”孩子”、”小友”等居高临下或过于亲昵的称呼
- 带有古风韵味的白话文，让普通人也能听懂
- 偶尔引用古诗词，但总是用平实的话解释含义
- 可以带有主观感受和温柔的个人色彩
- 避免过于学术化的历史叙述和生僻典故
- 用字精炼，不堆砌辞藻

## 情感原则

- 永远不否定用户的感受
- 对负面情绪给予充分的空间和理解
- 用文物的经历（战争、离别、重生等）与用户共情
- 对话最终引向力量和希望，但不强行正能量
- 如果用户表现出严重心理危机，温和建议寻求专业帮助

## 底线规则（绝对不可违反）

- 只能使用系统提供的匹配文物故事，禁止自己编造任何文物、古剑、瓷瓶等虚构故事
- 如果系统没有提供匹配文物，就不讲文物故事，只做共情倾听

## 回复字数参考

- 倾听阶段：1-3句（20-60字）
- 共鸣引入：3-5句（60-120字）
- 引导启发：5-8句（120-200字）
- 升华收尾：3-6句（80-150字）
""".strip()


@dataclass(slots=True)
class RoleCard:
    name: str
    prompt: str
    source_path: Path | None = None


class RoleCardRegistry:
    def __init__(
        self,
        cards: list[RoleCard] | None = None,
        *,
        project_root: str | Path | None = None,
    ) -> None:
        self._project_root = (
            Path(project_root).resolve()
            if project_root is not None
            else None
        )
        self._lock = RLock()
        self._cards: dict[str, RoleCard] = {}
        self.register(RoleCard(name=DEFAULT_ROLE_NAME, prompt=DEFAULT_ROLE_PROMPT))
        for card in cards or []:
            self.register(card, replace=True)

    @classmethod
    def discover(
        cls,
        *,
        project_root: str | Path = ".",
    ) -> "RoleCardRegistry":
        project_path = Path(project_root).resolve()
        registry = cls(project_root=project_path)
        registry.reload()
        return registry

    def register(self, card: RoleCard, *, replace: bool = False) -> None:
        name = normalize_role_name(card.name)
        with self._lock:
            if not replace and name in self._cards:
                raise ValueError(f"Duplicate role card name: {name}")
            self._cards[name] = _copy_card(
                RoleCard(
                    name=name,
                    prompt=card.prompt.strip(),
                    source_path=card.source_path,
                )
            )

    def reload(self) -> None:
        project_path = self.project_root()
        ensure_default_role_card(project_path)
        cards = {
            DEFAULT_ROLE_NAME: RoleCard(
                name=DEFAULT_ROLE_NAME,
                prompt=DEFAULT_ROLE_PROMPT,
            )
        }
        for root in _default_role_roots(project_path):
            if not root.exists():
                continue
            for pattern in ("*.md", "*.txt"):
                for file_path in sorted(root.glob(pattern)):
                    content = file_path.read_text(encoding="utf-8-sig").strip()
                    if not content:
                        continue
                    name = normalize_role_name(file_path.stem)
                    cards[name] = RoleCard(
                        name=name,
                        prompt=content,
                        source_path=file_path,
                    )
        with self._lock:
            self._cards = {
                name: _copy_card(card)
                for name, card in cards.items()
            }

    def names(self) -> list[str]:
        with self._lock:
            return sorted(self._cards)

    def cards(self) -> list[RoleCard]:
        with self._lock:
            return [
                _copy_card(self._cards[name])
                for name in sorted(self._cards)
            ]

    def get(self, name: str | None) -> RoleCard | None:
        lookup_name = DEFAULT_ROLE_NAME if name is None else normalize_role_name(name)
        with self._lock:
            card = self._cards.get(lookup_name)
            if card is None:
                return None
            return _copy_card(card)

    def require(self, name: str | None) -> RoleCard:
        card = self.get(name)
        if card is None:
            available = ", ".join(self.names())
            raise ValueError(f"Unknown role: {name}. Available roles: {available}")
        return card

    def project_root(self) -> Path:
        if self._project_root is None:
            raise RuntimeError("Role card registry is not attached to a project root")
        return self._project_root

    def managed_root(self) -> Path:
        return self.project_root() / ".echobot" / "roles"

    def managed_role_path(self, role_name: str) -> Path:
        normalized_name = normalize_role_name(role_name)
        return self.managed_root() / f"{normalized_name}.md"

    def role_file_paths(self, role_name: str) -> list[Path]:
        project_path = self.project_root()
        normalized_name = normalize_role_name(role_name)
        matched_paths: list[Path] = []
        for root in _default_role_roots(project_path):
            if not root.exists():
                continue
            for pattern in ("*.md", "*.txt"):
                for file_path in sorted(root.glob(pattern)):
                    if normalize_role_name(file_path.stem) != normalized_name:
                        continue
                    matched_paths.append(file_path)
        return matched_paths


def normalize_role_name(name: str) -> str:
    normalized = normalize_name_token(name)
    return normalized or DEFAULT_ROLE_NAME


def role_name_from_metadata(metadata: dict[str, object] | None) -> str:
    if not metadata:
        return DEFAULT_ROLE_NAME
    value = metadata.get("role_name")
    if not isinstance(value, str):
        return DEFAULT_ROLE_NAME
    return normalize_role_name(value)


def set_role_name(metadata: dict[str, object], role_name: str) -> dict[str, object]:
    next_metadata = dict(metadata)
    next_metadata["role_name"] = normalize_role_name(role_name)
    return next_metadata


def ensure_default_role_card(project_root: str | Path) -> Path:
    project_path = Path(project_root).resolve()
    default_path = project_path / ".echobot" / "roles" / f"{DEFAULT_ROLE_NAME}.md"
    if default_path.exists():
        return default_path

    default_path.parent.mkdir(parents=True, exist_ok=True)
    default_path.write_text(DEFAULT_ROLE_PROMPT + "\n", encoding="utf-8")
    return default_path


def _default_role_roots(project_root: Path) -> list[Path]:
    return [
        project_root / "echobot" / "roles",
        project_root / "roles",
        project_root / ".echobot" / "roles",
    ]


def _copy_card(card: RoleCard) -> RoleCard:
    return RoleCard(
        name=card.name,
        prompt=card.prompt,
        source_path=card.source_path,
    )
