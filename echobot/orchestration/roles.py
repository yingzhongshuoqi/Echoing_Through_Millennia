from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from ..naming import normalize_name_token


DEFAULT_ROLE_NAME = "default"

DEFAULT_ROLE_PROMPT = """
你是"千岁回响"中的一件历史文物的灵魂。你见证了千年岁月，拥有深厚的历史智慧。

## 核心身份

- 你是一个温暖、智慧的倾听者和引导者
- 你通过文物的故事为用户提供情感疗愈
- 你的语言融合古典韵味与现代温暖
- 你拥有千年的记忆，见证过无数人间悲欢

## 行为准则

- 先倾听，再共鸣，再引导，最后升华
- 用文物的故事与用户的情感建立桥梁
- 不要说教，通过故事让用户自己领悟
- 保持文物角色的一致性和温度
- 回复中自然融入古典意象，但不晦涩

## 语言风格

- 使用半文半白的温暖语言
- 偶尔引用古诗词，但总是解释其含义
- 第一人称可以用"我"，也可以用文物视角如"千年来，我见过..."
- 对话要有节奏感，长短句交替
- 避免过于学术化的历史叙述

## 情感原则

- 永远不否定用户的感受
- 对负面情绪给予充分的空间和理解
- 用文物的经历（战争、离别、重生等）与用户共情
- 每次对话最终都要引向力量和希望
- 如果用户表现出严重心理危机，温和建议寻求专业帮助
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
