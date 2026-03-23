from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from typing import Any

from ..models import LLMMessage
from ..providers.base import LLMProvider
from .emotion_models import DialoguePhase, EmotionResult

logger = logging.getLogger(__name__)

EMOTION_ANALYSIS_PROMPT = """你是一个专业的心理情感分析师。请分析用户输入的情感状态，并以JSON格式返回结果。

分析维度：
1. primary: 主要情感（如：喜悦、悲伤、焦虑、愤怒、失落、孤独、迷茫、怀念、平静、不甘、释然、敬畏等）
2. secondary: 次要情感/细微差异
3. intensity: 情感强度（1-10）
4. need: 潜在心理需求（如：被理解、被接纳、获得力量、寻找意义、获得安慰、重建信心、找到方向、学会放下、获得勇气、找到归属）
5. keywords: 情感关键词列表（3-5个与情感相关的关键词，用于匹配文物故事）
6. phase: 对话阶段判断（listening=需要倾听共情、resonance=可以引入共鸣、guiding=可以引导启发、elevation=可以升华总结）

仅返回JSON，不要有其他内容：
{"primary": "", "secondary": "", "intensity": 0, "need": "", "keywords": [], "phase": ""}"""


class EmotionAnalyzer:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def analyze(
        self,
        user_input: str,
        history: Sequence[LLMMessage] | None = None,
        turn_count: int = 0,
    ) -> EmotionResult:
        messages = self._build_messages(user_input, history, turn_count)
        try:
            response = await self._provider.generate(
                messages, temperature=0.3, max_tokens=512,
            )
            text = response.message.content_text.strip()
            return self._parse_result(text, turn_count)
        except Exception:
            logger.exception("Emotion analysis failed, using fallback")
            return self._fallback_analysis(user_input, turn_count)

    def _build_messages(
        self,
        user_input: str,
        history: Sequence[LLMMessage] | None,
        turn_count: int,
    ) -> list[LLMMessage]:
        messages = [LLMMessage(role="system", content=EMOTION_ANALYSIS_PROMPT)]

        if history:
            context_lines = []
            for h in history[-6:]:
                role_label = "用户" if h.role == "user" else "AI"
                context_lines.append(f"{role_label}: {h.content_text}")
            context = "\n".join(context_lines)
            messages.append(LLMMessage(
                role="user",
                content=f"对话历史（最近几轮）：\n{context}\n\n当前用户输入：{user_input}\n\n这是第{turn_count+1}轮对话，请分析当前情感状态。",
            ))
        else:
            messages.append(LLMMessage(
                role="user",
                content=f"用户输入：{user_input}\n\n这是第1轮对话，请分析情感状态。",
            ))
        return messages

    def _parse_result(self, text: str, turn_count: int) -> EmotionResult:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            data: dict[str, Any] = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Failed to parse emotion JSON: %s", cleaned[:200])
            return EmotionResult(raw_analysis=cleaned)

        phase = self._infer_phase(data.get("phase", ""), turn_count, data.get("intensity", 5))
        return EmotionResult(
            primary=data.get("primary", "平静"),
            secondary=data.get("secondary", ""),
            intensity=max(1, min(10, int(data.get("intensity", 5)))),
            need=data.get("need", ""),
            phase=phase,
            keywords=data.get("keywords", []),
            raw_analysis=cleaned,
        )

    def _infer_phase(self, phase_str: str, turn_count: int, intensity: int) -> DialoguePhase:
        phase_map = {
            "listening": DialoguePhase.LISTENING,
            "resonance": DialoguePhase.RESONANCE,
            "guiding": DialoguePhase.GUIDING,
            "elevation": DialoguePhase.ELEVATION,
        }
        if phase_str in phase_map:
            return phase_map[phase_str]
        if turn_count <= 1:
            return DialoguePhase.LISTENING
        elif turn_count <= 3:
            return DialoguePhase.RESONANCE
        elif turn_count <= 6:
            return DialoguePhase.GUIDING
        else:
            return DialoguePhase.ELEVATION

    def _fallback_analysis(self, user_input: str, turn_count: int) -> EmotionResult:
        negative_keywords = {"难过", "伤心", "痛苦", "失望", "焦虑", "害怕", "孤独", "迷茫", "烦", "累", "苦"}
        positive_keywords = {"开心", "高兴", "喜欢", "快乐", "感谢", "美好", "幸福", "满足"}

        primary = "平静"
        intensity = 5
        for w in negative_keywords:
            if w in user_input:
                primary = "失落"
                intensity = 6
                break
        for w in positive_keywords:
            if w in user_input:
                primary = "喜悦"
                intensity = 6
                break

        return EmotionResult(
            primary=primary,
            intensity=intensity,
            phase=self._infer_phase("", turn_count, intensity),
            keywords=[primary],
        )
