from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DialoguePhase(str, Enum):
    LISTENING = "listening"
    RESONANCE = "resonance"
    GUIDING = "guiding"
    ELEVATION = "elevation"


PRIMARY_EMOTIONS = [
    "喜悦", "兴奋", "感动", "满足", "希望", "感恩",
    "悲伤", "失落", "孤独", "思念", "遗憾", "无助",
    "焦虑", "恐惧", "不安", "迷茫", "压抑", "烦躁",
    "愤怒", "不甘", "委屈", "嫉妒", "怨恨",
    "平静", "释然", "淡然", "怀念", "敬畏", "好奇",
]

SECONDARY_EMOTION_MAP: dict[str, list[str]] = {
    "喜悦": ["欣慰", "满足", "自豪", "幸福"],
    "兴奋": ["激动", "期待", "热情", "振奋"],
    "悲伤": ["哀伤", "心痛", "凄凉", "惆怅"],
    "失落": ["空虚", "落寞", "茫然", "沮丧"],
    "孤独": ["寂寞", "疏离", "被遗忘", "隔阂"],
    "焦虑": ["紧张", "忧虑", "担心", "惶恐"],
    "愤怒": ["气愤", "暴躁", "激愤", "恼怒"],
    "不甘": ["执念", "倔强", "不服", "抗争"],
    "迷茫": ["困惑", "彷徨", "不知所措", "纠结"],
    "怀念": ["思念", "追忆", "眷恋", "留恋"],
    "平静": ["安宁", "从容", "淡定", "宁静"],
    "释然": ["放下", "解脱", "豁达", "通透"],
    "敬畏": ["崇敬", "仰慕", "赞叹", "震撼"],
}

PSYCHOLOGICAL_NEEDS = [
    "被理解", "被接纳", "获得力量", "寻找意义",
    "获得安慰", "重建信心", "找到方向", "学会放下",
    "获得勇气", "找到归属", "自我认同", "情感释放",
]


@dataclass(slots=True)
class EmotionResult:
    primary: str = "平静"
    secondary: str = ""
    intensity: int = 5
    need: str = ""
    phase: DialoguePhase = DialoguePhase.LISTENING
    keywords: list[str] = field(default_factory=list)
    raw_analysis: str = ""

    def to_dict(self) -> dict:
        return {
            "primary": self.primary,
            "secondary": self.secondary,
            "intensity": self.intensity,
            "need": self.need,
            "phase": self.phase.value,
            "keywords": self.keywords,
        }

    @classmethod
    def from_dict(cls, data: dict) -> EmotionResult:
        return cls(
            primary=data.get("primary", "平静"),
            secondary=data.get("secondary", ""),
            intensity=data.get("intensity", 5),
            need=data.get("need", ""),
            phase=DialoguePhase(data.get("phase", "listening")),
            keywords=data.get("keywords", []),
        )
