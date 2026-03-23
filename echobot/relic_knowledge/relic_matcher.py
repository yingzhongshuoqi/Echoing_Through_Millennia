from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from .emotion_models import EmotionResult
from .retriever import RelicMatch, RelicRetriever

logger = logging.getLogger(__name__)


class RelicMatcher:
    """基于 Plutchik 情绪轮盘的文物语义匹配。"""

    def __init__(self, retriever: RelicRetriever) -> None:
        self._retriever = retriever

    async def match(
        self,
        db: AsyncSession,
        emotion: EmotionResult,
        used_relic_ids: Sequence[int] | None = None,
    ) -> RelicMatch | None:
        query_text = self._build_query(emotion)
        tag_keywords = self._emotion_to_tag_keywords(emotion)

        matches = await self._retriever.search_by_emotion(
            db,
            query_text=query_text,
            keywords=tag_keywords,
            limit=5,
        )

        if used_relic_ids:
            used_set = set(used_relic_ids)
            matches = [m for m in matches if m.relic.id not in used_set]

        if not matches:
            random_matches = await self._retriever.get_random(db, limit=1)
            return random_matches[0] if random_matches else None

        return matches[0]

    def _build_query(self, emotion: EmotionResult) -> str:
        """利用 Plutchik 丰富数据构建语义查询文本。"""
        parts: list[str] = []

        # 主导情绪：使用强度层级中文名（比基本名更具表现力）
        for de in emotion.dominant_emotions[:2]:
            intensity_cn = de.get("intensity_name_cn", "")
            cn = de.get("cn", "")
            if intensity_cn:
                parts.append(intensity_cn)
            elif cn:
                parts.append(cn)

        # 复合情绪中文名（Dyads 更贴合复杂情感场景）
        for dyad in emotion.active_dyads[:2]:
            cn = dyad.get("name_cn", "")
            if cn:
                parts.append(cn)

        # 心理需求
        if emotion.need:
            parts.append(emotion.need)

        # 关键词
        parts.extend(emotion.keywords[:3])

        return " ".join(parts) if parts else "平静"

    def _emotion_to_tag_keywords(self, emotion: EmotionResult) -> list[str]:
        """从 Plutchik 分析结果提取关键词，用于文物 emotion_tags 匹配。"""
        tags: list[str] = []

        for de in emotion.dominant_emotions[:3]:
            cn = de.get("cn", "")
            if cn:
                tags.append(cn)
            intensity_cn = de.get("intensity_name_cn", "")
            if intensity_cn and intensity_cn != cn:
                tags.append(intensity_cn)

        for dyad in emotion.active_dyads[:2]:
            cn = dyad.get("name_cn", "")
            if cn:
                tags.append(cn)

        tags.extend(emotion.keywords)

        # 去重保序
        seen: set[str] = set()
        unique: list[str] = []
        for t in tags:
            if t and t not in seen:
                seen.add(t)
                unique.append(t)
        return unique
