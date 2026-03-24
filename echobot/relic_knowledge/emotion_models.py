"""Plutchik's Wheel of Emotions — 核心数据模型.

基于罗伯特·普拉奇克情绪轮盘理论：
- 8 种基本情绪，4 组对立关系
- 每种情绪 3 个强度层级（mild / basic / intense）
- 相邻/相隔情绪组合产生 24 种复合情绪（Dyads）
- 8 维情绪向量表征情感状态
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ──────────────────────────────────────────────
# 枚举定义
# ──────────────────────────────────────────────

class PlutchikEmotion(str, Enum):
    """8 种基本情绪，按轮盘顺时针排列。"""
    JOY = "joy"
    TRUST = "trust"
    FEAR = "fear"
    SURPRISE = "surprise"
    SADNESS = "sadness"
    DISGUST = "disgust"
    ANGER = "anger"
    ANTICIPATION = "anticipation"


class IntensityLevel(str, Enum):
    """情绪强度三层级。"""
    MILD = "mild"        # 外层（弱）
    BASIC = "basic"      # 中层（基本）
    INTENSE = "intense"  # 内层（强烈）


class DialoguePhase(str, Enum):
    """四阶段引导对话。"""
    LISTENING = "listening"
    RESONANCE = "resonance"
    GUIDING = "guiding"
    ELEVATION = "elevation"


# ──────────────────────────────────────────────
# 轮盘顺序 & 颜色
# ──────────────────────────────────────────────

WHEEL_ORDER: tuple[PlutchikEmotion, ...] = (
    PlutchikEmotion.JOY,
    PlutchikEmotion.TRUST,
    PlutchikEmotion.FEAR,
    PlutchikEmotion.SURPRISE,
    PlutchikEmotion.SADNESS,
    PlutchikEmotion.DISGUST,
    PlutchikEmotion.ANGER,
    PlutchikEmotion.ANTICIPATION,
)

EMOTION_COLORS: dict[PlutchikEmotion, str] = {
    PlutchikEmotion.JOY: "#FFEB3B",
    PlutchikEmotion.TRUST: "#8BC34A",
    PlutchikEmotion.FEAR: "#4CAF50",
    PlutchikEmotion.SURPRISE: "#00BCD4",
    PlutchikEmotion.SADNESS: "#2196F3",
    PlutchikEmotion.DISGUST: "#9C27B0",
    PlutchikEmotion.ANGER: "#F44336",
    PlutchikEmotion.ANTICIPATION: "#FF9800",
}


# ──────────────────────────────────────────────
# PLUTCHIK_WHEEL — 完整轮盘数据
# ──────────────────────────────────────────────

PLUTCHIK_WHEEL: dict[str, Any] = {
    # ── 8 种基本情绪定义 ──
    "emotions": {
        PlutchikEmotion.JOY: {
            "cn": "快乐",
            "color": "#FFEB3B",
            "opposite": PlutchikEmotion.SADNESS,
            "intensities": {
                IntensityLevel.MILD:    {"en": "serenity",    "cn": "宁静"},
                IntensityLevel.BASIC:   {"en": "joy",         "cn": "快乐"},
                IntensityLevel.INTENSE: {"en": "ecstasy",     "cn": "狂喜"},
            },
        },
        PlutchikEmotion.TRUST: {
            "cn": "信任",
            "color": "#8BC34A",
            "opposite": PlutchikEmotion.DISGUST,
            "intensities": {
                IntensityLevel.MILD:    {"en": "acceptance",  "cn": "接受"},
                IntensityLevel.BASIC:   {"en": "trust",       "cn": "信任"},
                IntensityLevel.INTENSE: {"en": "admiration",  "cn": "崇敬"},
            },
        },
        PlutchikEmotion.FEAR: {
            "cn": "恐惧",
            "color": "#4CAF50",
            "opposite": PlutchikEmotion.ANGER,
            "intensities": {
                IntensityLevel.MILD:    {"en": "apprehension", "cn": "忧虑"},
                IntensityLevel.BASIC:   {"en": "fear",         "cn": "恐惧"},
                IntensityLevel.INTENSE: {"en": "terror",       "cn": "恐怖"},
            },
        },
        PlutchikEmotion.SURPRISE: {
            "cn": "惊讶",
            "color": "#00BCD4",
            "opposite": PlutchikEmotion.ANTICIPATION,
            "intensities": {
                IntensityLevel.MILD:    {"en": "distraction", "cn": "分心"},
                IntensityLevel.BASIC:   {"en": "surprise",    "cn": "惊讶"},
                IntensityLevel.INTENSE: {"en": "amazement",   "cn": "惊愕"},
            },
        },
        PlutchikEmotion.SADNESS: {
            "cn": "悲伤",
            "color": "#2196F3",
            "opposite": PlutchikEmotion.JOY,
            "intensities": {
                IntensityLevel.MILD:    {"en": "pensiveness", "cn": "忧伤"},
                IntensityLevel.BASIC:   {"en": "sadness",     "cn": "悲伤"},
                IntensityLevel.INTENSE: {"en": "grief",       "cn": "悲痛"},
            },
        },
        PlutchikEmotion.DISGUST: {
            "cn": "厌恶",
            "color": "#9C27B0",
            "opposite": PlutchikEmotion.TRUST,
            "intensities": {
                IntensityLevel.MILD:    {"en": "boredom",  "cn": "无趣"},
                IntensityLevel.BASIC:   {"en": "disgust",  "cn": "厌恶"},
                IntensityLevel.INTENSE: {"en": "loathing", "cn": "嫌恶"},
            },
        },
        PlutchikEmotion.ANGER: {
            "cn": "愤怒",
            "color": "#F44336",
            "opposite": PlutchikEmotion.FEAR,
            "intensities": {
                IntensityLevel.MILD:    {"en": "annoyance", "cn": "烦扰"},
                IntensityLevel.BASIC:   {"en": "anger",     "cn": "愤怒"},
                IntensityLevel.INTENSE: {"en": "rage",      "cn": "暴怒"},
            },
        },
        PlutchikEmotion.ANTICIPATION: {
            "cn": "期待",
            "color": "#FF9800",
            "opposite": PlutchikEmotion.SURPRISE,
            "intensities": {
                IntensityLevel.MILD:    {"en": "interest",   "cn": "兴趣"},
                IntensityLevel.BASIC:   {"en": "anticipation", "cn": "期待"},
                IntensityLevel.INTENSE: {"en": "vigilance",  "cn": "警觉"},
            },
        },
    },

    # ── 初级配对（相邻情绪组合）──
    "primary_dyads": {
        frozenset(("joy", "trust")):          {"en": "love",           "cn": "爱"},
        frozenset(("trust", "fear")):         {"en": "submission",     "cn": "顺从"},
        frozenset(("fear", "surprise")):      {"en": "awe",            "cn": "敬畏"},
        frozenset(("surprise", "sadness")):   {"en": "disapproval",    "cn": "不赞同"},
        frozenset(("sadness", "disgust")):    {"en": "remorse",        "cn": "悔恨"},
        frozenset(("disgust", "anger")):      {"en": "contempt",       "cn": "鄙视"},
        frozenset(("anger", "anticipation")): {"en": "aggressiveness", "cn": "好斗"},
        frozenset(("anticipation", "joy")):   {"en": "optimism",       "cn": "乐观"},
    },

    # ── 二级配对（相隔两位组合）──
    "secondary_dyads": {
        frozenset(("joy", "fear")):           {"en": "guilt",      "cn": "内疚"},
        frozenset(("trust", "surprise")):     {"en": "curiosity",  "cn": "好奇"},
        frozenset(("fear", "sadness")):       {"en": "despair",    "cn": "绝望"},
        frozenset(("surprise", "disgust")):   {"en": "unbelief",   "cn": "难以置信"},
        frozenset(("sadness", "anger")):      {"en": "envy",       "cn": "嫉妒"},
        frozenset(("disgust", "anticipation")): {"en": "cynicism", "cn": "愤世嫉俗"},
        frozenset(("anger", "joy")):          {"en": "pride",      "cn": "骄傲"},
        frozenset(("anticipation", "trust")): {"en": "hope",       "cn": "希望"},
    },

    # ── 三级配对（相隔三位组合）──
    "tertiary_dyads": {
        frozenset(("joy", "surprise")):       {"en": "delight",        "cn": "欣喜"},
        frozenset(("trust", "sadness")):      {"en": "sentimentality", "cn": "感伤"},
        frozenset(("fear", "disgust")):       {"en": "shame",          "cn": "羞耻"},
        frozenset(("surprise", "anger")):     {"en": "outrage",        "cn": "义愤"},
        frozenset(("sadness", "anticipation")): {"en": "pessimism",    "cn": "悲观"},
        frozenset(("disgust", "joy")):        {"en": "morbidness",     "cn": "病态"},
        frozenset(("anger", "trust")):        {"en": "dominance",      "cn": "支配"},
        frozenset(("anticipation", "fear")):  {"en": "anxiety",        "cn": "焦虑"},
    },
}

# 4 组对立关系
OPPOSITE_PAIRS: list[tuple[PlutchikEmotion, PlutchikEmotion]] = [
    (PlutchikEmotion.JOY, PlutchikEmotion.SADNESS),
    (PlutchikEmotion.TRUST, PlutchikEmotion.DISGUST),
    (PlutchikEmotion.FEAR, PlutchikEmotion.ANGER),
    (PlutchikEmotion.SURPRISE, PlutchikEmotion.ANTICIPATION),
]


# ──────────────────────────────────────────────
# EmotionVector — 8 维情绪向量
# ──────────────────────────────────────────────

@dataclass(slots=True)
class EmotionVector:
    """8 维浮点向量，每维 ∈ [0.0, 1.0]，对应一种基本情绪。"""

    joy: float = 0.0
    trust: float = 0.0
    fear: float = 0.0
    surprise: float = 0.0
    sadness: float = 0.0
    disgust: float = 0.0
    anger: float = 0.0
    anticipation: float = 0.0

    # ── 序列化 ──

    def to_list(self) -> list[float]:
        """按 WHEEL_ORDER 返回分数列表。"""
        return [getattr(self, e.value) for e in WHEEL_ORDER]

    @classmethod
    def from_list(cls, values: list[float]) -> EmotionVector:
        if len(values) != 8:
            raise ValueError(f"Expected 8 values, got {len(values)}")
        kwargs = {e.value: max(0.0, min(1.0, float(v))) for e, v in zip(WHEEL_ORDER, values)}
        return cls(**kwargs)

    def to_dict(self) -> dict[str, float]:
        return {e.value: round(getattr(self, e.value), 4) for e in WHEEL_ORDER}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EmotionVector:
        kwargs = {}
        for e in WHEEL_ORDER:
            raw = data.get(e.value, 0.0)
            kwargs[e.value] = max(0.0, min(1.0, float(raw)))
        return cls(**kwargs)

    # ── 主导情绪 ──

    def dominant_emotions(
        self, threshold: float = 0.3, top_n: int = 3,
    ) -> list[tuple[PlutchikEmotion, float]]:
        """返回高于阈值的主导情绪，按分数降序，最多 top_n 个。"""
        pairs = [
            (e, getattr(self, e.value))
            for e in WHEEL_ORDER
            if getattr(self, e.value) >= threshold
        ]
        pairs.sort(key=lambda p: p[1], reverse=True)
        return pairs[:top_n]

    # ── 复合情绪（Dyads）──

    def compute_dyads(self, threshold: float = 0.25) -> list[dict[str, Any]]:
        """检测激活的复合情绪。两种成分分数都 > threshold 时触发。"""
        results: list[dict[str, Any]] = []
        for dyad_type in ("primary_dyads", "secondary_dyads", "tertiary_dyads"):
            dyad_map = PLUTCHIK_WHEEL[dyad_type]
            for pair_key, info in dyad_map.items():
                components = list(pair_key)
                score_a = getattr(self, components[0], 0.0)
                score_b = getattr(self, components[1], 0.0)
                if score_a >= threshold and score_b >= threshold:
                    combined = min(score_a, score_b)
                    results.append({
                        "type": dyad_type.replace("_dyads", ""),
                        "name_en": info["en"],
                        "name_cn": info["cn"],
                        "score": round(combined, 4),
                        "components": components,
                    })
        results.sort(key=lambda d: d["score"], reverse=True)
        return results

    # ── 强度级别 ──

    def intensity_level(self) -> IntensityLevel:
        """根据最大分数判断强度层级。"""
        max_score = max(self.to_list()) if any(v > 0 for v in self.to_list()) else 0.0
        if max_score >= 0.7:
            return IntensityLevel.INTENSE
        elif max_score >= 0.4:
            return IntensityLevel.BASIC
        return IntensityLevel.MILD

    # ── 对立冲突 ──

    def opposite_tension(self) -> list[dict[str, Any]]:
        """检测对立情绪对同时激活的冲突。"""
        tensions = []
        for emo_a, emo_b in OPPOSITE_PAIRS:
            score_a = getattr(self, emo_a.value, 0.0)
            score_b = getattr(self, emo_b.value, 0.0)
            if score_a >= 0.25 and score_b >= 0.25:
                tension_val = min(score_a, score_b)
                wheel_data = PLUTCHIK_WHEEL["emotions"]
                tensions.append({
                    "pair": [wheel_data[emo_a]["cn"], wheel_data[emo_b]["cn"]],
                    "pair_en": [emo_a.value, emo_b.value],
                    "tension": round(tension_val, 4),
                })
        tensions.sort(key=lambda t: t["tension"], reverse=True)
        return tensions

    # ── 向量距离 ──

    def cosine_distance(self, other: EmotionVector) -> float:
        """余弦距离，用于情绪轨迹对比。0 = 完全相同，1 = 完全不同。"""
        a = self.to_list()
        b = other.to_list()
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 1.0
        similarity = dot / (norm_a * norm_b)
        return round(1.0 - max(-1.0, min(1.0, similarity)), 4)

    # ── 最大分数 ──

    def max_score(self) -> float:
        vals = self.to_list()
        return max(vals) if vals else 0.0


# ──────────────────────────────────────────────
# 辅助函数 — 从向量构建富化的主导情绪信息
# ──────────────────────────────────────────────

def enrich_dominant_emotions(
    dominants: list[tuple[PlutchikEmotion, float]],
) -> list[dict[str, Any]]:
    """为主导情绪附加中文名、强度层级名称、颜色等信息。"""
    wheel = PLUTCHIK_WHEEL["emotions"]
    enriched = []
    for emo, score in dominants:
        emo_data = wheel[emo]
        if score >= 0.7:
            level = IntensityLevel.INTENSE
        elif score >= 0.4:
            level = IntensityLevel.BASIC
        else:
            level = IntensityLevel.MILD
        level_info = emo_data["intensities"][level]
        enriched.append({
            "emotion": emo.value,
            "score": round(score, 4),
            "cn": emo_data["cn"],
            "color": emo_data["color"],
            "intensity_name_cn": level_info["cn"],
            "intensity_name_en": level_info["en"],
            "intensity_level": level.value,
        })
    return enriched


# ──────────────────────────────────────────────
# EmotionResult — 情感分析结果
# ──────────────────────────────────────────────

@dataclass(slots=True)
class EmotionResult:
    """普拉奇克情绪轮盘分析结果。"""

    # Plutchik 核心
    emotion_vector: EmotionVector = field(default_factory=EmotionVector)
    dominant_emotions: list[dict[str, Any]] = field(default_factory=list)
    active_dyads: list[dict[str, Any]] = field(default_factory=list)
    intensity_level: IntensityLevel = IntensityLevel.BASIC
    opposite_tensions: list[dict[str, Any]] = field(default_factory=list)

    # 对话阶段
    phase: DialoguePhase = DialoguePhase.LISTENING

    # 调试
    raw_analysis: str = ""

    # ── 兼容性属性 ──

    @property
    def primary(self) -> str:
        """主导情绪中文名（向后兼容）。"""
        if self.dominant_emotions:
            return self.dominant_emotions[0].get("cn", "平静")
        return "平静"

    @property
    def secondary(self) -> str:
        """次要情绪中文名（向后兼容）。"""
        if len(self.dominant_emotions) > 1:
            return self.dominant_emotions[1].get("cn", "")
        return ""

    @property
    def intensity(self) -> int:
        """1-10 强度整数（向后兼容）。"""
        max_val = self.emotion_vector.max_score()
        return max(1, min(10, round(max_val * 10)))

    # ── 序列化 ──

    def to_dict(self) -> dict[str, Any]:
        return {
            # Plutchik 核心
            "emotion_vector": self.emotion_vector.to_dict(),
            "dominant_emotions": self.dominant_emotions,
            "active_dyads": self.active_dyads,
            "intensity_level": self.intensity_level.value,
            "opposite_tensions": self.opposite_tensions,
            "phase": self.phase.value,
            # 向后兼容
            "primary": self.primary,
            "secondary": self.secondary,
            "intensity": self.intensity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EmotionResult:
        vec = EmotionVector.from_dict(data.get("emotion_vector", {}))

        dominants = data.get("dominant_emotions", [])
        if not dominants:
            raw_dominants = vec.dominant_emotions()
            dominants = enrich_dominant_emotions(raw_dominants)

        dyads = data.get("active_dyads", [])
        if not dyads:
            dyads = vec.compute_dyads()

        il_str = data.get("intensity_level", "basic")
        try:
            il = IntensityLevel(il_str)
        except ValueError:
            il = IntensityLevel.BASIC

        phase_str = data.get("phase", "listening")
        try:
            phase = DialoguePhase(phase_str)
        except ValueError:
            phase = DialoguePhase.LISTENING

        return cls(
            emotion_vector=vec,
            dominant_emotions=dominants,
            active_dyads=dyads,
            intensity_level=il,
            opposite_tensions=data.get("opposite_tensions", []),
            phase=phase,
        )
