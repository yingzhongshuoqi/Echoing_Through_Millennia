"""LLM 驱动的普拉奇克情绪轮盘分析器.

利用 LLM 对用户输入进行 8 维情绪评分，随后在 Python 侧确定性计算
复合情绪(Dyads)、强度层级、对立冲突和对话阶段。
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence
from typing import Any

from ..models import LLMMessage
from ..providers.base import LLMProvider
from .emotion_models import (
    DialoguePhase,
    EmotionResult,
    EmotionVector,
    IntensityLevel,
    PLUTCHIK_WHEEL,
    WHEEL_ORDER,
    enrich_dominant_emotions,
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# System Prompt — 教导 LLM 普拉奇克模型
# ──────────────────────────────────────────────

PLUTCHIK_ANALYSIS_PROMPT = """你是一位基于普拉奇克情绪轮盘(Plutchik's Wheel of Emotions)模型的专业心理情感分析师。

## 普拉奇克情绪轮盘模型

8种基本情绪（按轮盘顺序），每种有3个强度层级（弱→基本→强）：
1. Joy 快乐 — 宁静 → 快乐 → 狂喜
2. Trust 信任 — 接受 → 信任 → 崇敬
3. Fear 恐惧 — 忧虑 → 恐惧 → 恐怖
4. Surprise 惊讶 — 分心 → 惊讶 → 惊愕
5. Sadness 悲伤 — 忧伤 → 悲伤 → 悲痛
6. Disgust 厌恶 — 无趣 → 厌恶 → 嫌恶
7. Anger 愤怒 — 烦扰 → 愤怒 → 暴怒
8. Anticipation 期待 — 兴趣 → 期待 → 警觉

4组对立关系：快乐↔悲伤、信任↔厌恶、恐惧↔愤怒、惊讶↔期待

相邻情绪组合产生复合情绪：
- 快乐+信任=爱, 信任+恐惧=顺从, 恐惧+惊讶=敬畏, 惊讶+悲伤=不赞同
- 悲伤+厌恶=悔恨, 厌恶+愤怒=鄙视, 愤怒+期待=好斗, 期待+快乐=乐观

## 分析任务

请仔细阅读用户输入及对话上下文，为每种基本情绪打分（0.0-1.0）：
- 0.0 = 完全不存在
- 0.1-0.3 = 轻微存在
- 0.4-0.6 = 明显存在
- 0.7-1.0 = 非常强烈

同时识别用户的心理需求和情感关键词。

请严格按以下JSON格式返回，不要包含其他内容：
{"scores":{"joy":0.0,"trust":0.0,"fear":0.0,"surprise":0.0,"sadness":0.0,"disgust":0.0,"anger":0.0,"anticipation":0.0},"need":"心理需求描述","keywords":["关键词1","关键词2","关键词3"]}"""


# ──────────────────────────────────────────────
# 负面情绪集合（用于 phase 推断）
# ──────────────────────────────────────────────

_NEGATIVE_EMOTIONS = frozenset({"sadness", "fear", "anger", "disgust"})


# ──────────────────────────────────────────────
# EmotionAnalyzer
# ──────────────────────────────────────────────

class EmotionAnalyzer:
    """基于普拉奇克情绪轮盘的 LLM 情感分析器。"""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider
        self._trajectory: list[EmotionVector] = []

    async def analyze(
        self,
        user_input: str,
        history: Sequence[LLMMessage] | None = None,
        turn_count: int = 0,
    ) -> EmotionResult:
        """分析用户输入的情感状态，返回 EmotionResult。"""
        messages = self._build_messages(user_input, history, turn_count)
        try:
            response = await self._provider.generate(
                messages, temperature=0.2, max_tokens=256,
            )
            text = response.message.content_text.strip()
            return self._parse_result(text, turn_count)
        except Exception:
            logger.exception("Plutchik emotion analysis failed, using fallback")
            return self._fallback_analysis(user_input, turn_count)

    # ── 构建消息 ──

    def _build_messages(
        self,
        user_input: str,
        history: Sequence[LLMMessage] | None,
        turn_count: int,
    ) -> list[LLMMessage]:
        messages = [LLMMessage(role="system", content=PLUTCHIK_ANALYSIS_PROMPT)]

        if history:
            context_lines = []
            for h in history[-6:]:
                role_label = "用户" if h.role == "user" else "AI"
                context_lines.append(f"{role_label}: {h.content_text}")
            context = "\n".join(context_lines)
            messages.append(LLMMessage(
                role="user",
                content=(
                    f"对话历史（最近几轮）：\n{context}\n\n"
                    f"当前用户输入：{user_input}\n\n"
                    f"这是第{turn_count + 1}轮对话，请用普拉奇克模型分析当前情感状态。"
                ),
            ))
        else:
            messages.append(LLMMessage(
                role="user",
                content=(
                    f"用户输入：{user_input}\n\n"
                    f"这是第1轮对话，请用普拉奇克模型分析情感状态。"
                ),
            ))
        return messages

    # ── 解析 LLM 返回 ──

    def _parse_result(self, text: str, turn_count: int) -> EmotionResult:
        data = self._extract_json(text)
        if data is None:
            logger.warning("Failed to parse Plutchik JSON: %s", text[:200])
            return EmotionResult(raw_analysis=text)

        # 1. 构建 EmotionVector
        scores = data.get("scores", {})
        vec = EmotionVector.from_dict(scores)

        # 2. 计算主导情绪
        raw_dominants = vec.dominant_emotions(threshold=0.25, top_n=3)
        dominant_emotions = enrich_dominant_emotions(raw_dominants)

        # 3. 计算复合情绪
        active_dyads = vec.compute_dyads(threshold=0.2)

        # 4. 强度级别
        intensity_level = vec.intensity_level()

        # 5. 对立冲突
        opposite_tensions = vec.opposite_tension()

        # 6. 推断对话阶段
        phase = self._infer_phase(vec, turn_count)

        # 7. 更新轨迹
        self._trajectory.append(vec)
        if len(self._trajectory) > 10:
            self._trajectory = self._trajectory[-10:]

        # 8. 提取需求和关键词
        need = data.get("need", "")
        keywords = data.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [keywords]

        return EmotionResult(
            emotion_vector=vec,
            dominant_emotions=dominant_emotions,
            active_dyads=active_dyads,
            intensity_level=intensity_level,
            opposite_tensions=opposite_tensions,
            need=need,
            phase=phase,
            keywords=keywords,
            raw_analysis=text,
        )

    # ── JSON 提取（健壮） ──

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any] | None:
        """从 LLM 返回的文本中提取 JSON，处理 markdown 包裹等情况。"""
        cleaned = text.strip()

        # 直接尝试
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 去除 markdown 代码块
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # 去掉首行 ```json 和末行 ```
            start = 1
            end = len(lines)
            if lines[-1].strip() == "```":
                end = -1
            inner = "\n".join(lines[start:end])
            try:
                return json.loads(inner)
            except json.JSONDecodeError:
                pass

        # 正则提取 JSON 对象
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return None

    # ── 对话阶段推断 ──

    def _infer_phase(self, vec: EmotionVector, turn_count: int) -> DialoguePhase:
        """基于情绪动态和对话轮次推断对话阶段。"""
        # 第一轮永远是倾听
        if turn_count <= 0:
            return DialoguePhase.LISTENING

        # 高强度负面情绪 → 保持倾听（用户需要被听到）
        max_score = vec.max_score()
        if max_score >= 0.7:
            dominants = vec.dominant_emotions(threshold=0.6, top_n=1)
            if dominants and dominants[0][0].value in _NEGATIVE_EMOTIONS:
                return DialoguePhase.LISTENING

        # 有轨迹时：基于情绪动态
        if len(self._trajectory) >= 2:
            prev_vec = self._trajectory[-1]
            distance = vec.cosine_distance(prev_vec)
            prev_max = prev_vec.max_score()

            # 情绪趋稳（距离小）+ 足够轮次 → 可以引导
            if distance < 0.15 and turn_count >= 3:
                return DialoguePhase.GUIDING

            # 情绪强度持续下降 → 可以进入共鸣
            if max_score < prev_max and turn_count >= 2:
                return DialoguePhase.RESONANCE

            # 持续低强度 或 正面转向 → 升华
            if max_score < 0.4 and turn_count >= 4:
                return DialoguePhase.ELEVATION

            # 正面情绪占主导且稳定 → 升华
            if turn_count >= 5:
                joy_trust = vec.joy + vec.trust + vec.anticipation
                neg = vec.sadness + vec.fear + vec.anger + vec.disgust
                if joy_trust > neg and distance < 0.2:
                    return DialoguePhase.ELEVATION

        # 兜底：基于轮次
        if turn_count <= 1:
            return DialoguePhase.LISTENING
        elif turn_count <= 3:
            return DialoguePhase.RESONANCE
        elif turn_count <= 6:
            return DialoguePhase.GUIDING
        else:
            return DialoguePhase.ELEVATION

    # ── 关键词 Fallback ──

    def _fallback_analysis(self, user_input: str, turn_count: int) -> EmotionResult:
        """LLM 失败时的关键词回退分析。"""
        vec = EmotionVector()

        # 中文关键词 → Plutchik 维度映射
        _KEYWORD_MAP: dict[str, dict[str, float]] = {
            "难过": {"sadness": 0.6},
            "伤心": {"sadness": 0.7},
            "痛苦": {"sadness": 0.8, "anger": 0.2},
            "失望": {"sadness": 0.5, "disgust": 0.3},
            "失落": {"sadness": 0.6},
            "焦虑": {"fear": 0.5, "anticipation": 0.4},
            "害怕": {"fear": 0.7},
            "恐惧": {"fear": 0.8},
            "孤独": {"sadness": 0.5, "fear": 0.2},
            "迷茫": {"surprise": 0.3, "fear": 0.3},
            "烦": {"anger": 0.4, "disgust": 0.3},
            "累": {"sadness": 0.3, "disgust": 0.3},
            "苦": {"sadness": 0.5, "disgust": 0.2},
            "怒": {"anger": 0.7},
            "气": {"anger": 0.5},
            "愤怒": {"anger": 0.8},
            "不甘": {"anger": 0.5, "sadness": 0.3},
            "委屈": {"sadness": 0.5, "anger": 0.3},
            "嫉妒": {"sadness": 0.4, "anger": 0.4},
            "怨恨": {"anger": 0.6, "disgust": 0.3},
            "厌倦": {"disgust": 0.5, "sadness": 0.2},
            "恶心": {"disgust": 0.7},
            "开心": {"joy": 0.6},
            "高兴": {"joy": 0.6},
            "喜欢": {"joy": 0.4, "trust": 0.3},
            "快乐": {"joy": 0.7},
            "感谢": {"joy": 0.4, "trust": 0.5},
            "美好": {"joy": 0.5, "trust": 0.3},
            "幸福": {"joy": 0.8, "trust": 0.3},
            "满足": {"joy": 0.5, "trust": 0.2},
            "感动": {"joy": 0.5, "sadness": 0.2, "trust": 0.3},
            "希望": {"anticipation": 0.6, "trust": 0.3},
            "期待": {"anticipation": 0.7},
            "兴奋": {"joy": 0.5, "anticipation": 0.5},
            "好奇": {"surprise": 0.4, "trust": 0.3},
            "惊讶": {"surprise": 0.6},
            "震惊": {"surprise": 0.8},
            "敬畏": {"fear": 0.3, "surprise": 0.4, "trust": 0.3},
            "怀念": {"sadness": 0.3, "joy": 0.2, "anticipation": 0.2},
            "思念": {"sadness": 0.4, "joy": 0.2},
            "平静": {},
            "释然": {"joy": 0.3, "trust": 0.2},
        }

        # 逐词匹配，累加分数
        scores: dict[str, float] = {e.value: 0.0 for e in WHEEL_ORDER}
        matched_keywords: list[str] = []
        for keyword, mapping in _KEYWORD_MAP.items():
            if keyword in user_input:
                matched_keywords.append(keyword)
                for emo, val in mapping.items():
                    scores[emo] = min(1.0, scores[emo] + val)

        # 构建向量
        for emo in WHEEL_ORDER:
            setattr(vec, emo.value, min(1.0, scores[emo.value]))

        # 后处理
        raw_dominants = vec.dominant_emotions(threshold=0.2, top_n=3)
        dominant_emotions = enrich_dominant_emotions(raw_dominants)
        active_dyads = vec.compute_dyads(threshold=0.2)
        intensity_level = vec.intensity_level()
        opposite_tensions = vec.opposite_tension()
        phase = self._infer_phase(vec, turn_count)

        # 更新轨迹
        self._trajectory.append(vec)
        if len(self._trajectory) > 10:
            self._trajectory = self._trajectory[-10:]

        return EmotionResult(
            emotion_vector=vec,
            dominant_emotions=dominant_emotions,
            active_dyads=active_dyads,
            intensity_level=intensity_level,
            opposite_tensions=opposite_tensions,
            need="被理解" if matched_keywords else "",
            phase=phase,
            keywords=matched_keywords[:5] if matched_keywords else ["平静"],
        )
