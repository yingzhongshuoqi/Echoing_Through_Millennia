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
            emotion_vector=emotion.emotion_vector.to_list(),
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
        """仅使用 Plutchik 词表构建语义查询文本。"""
        parts: list[str] = []

        for de in emotion.dominant_emotions[:2]:
            intensity_cn = de.get("intensity_name_cn", "")
            cn = de.get("cn", "")
            if intensity_cn:
                parts.append(intensity_cn)
            elif cn:
                parts.append(cn)

        for dyad in emotion.active_dyads[:2]:
            cn = dyad.get("name_cn", "")
            if cn:
                parts.append(cn)

        return " ".join(parts) if parts else "平静"

    def _emotion_to_tag_keywords(self, emotion: EmotionResult) -> list[str]:
        """仅从 Plutchik 词表提取关键词，用于文物 emotion_tags 匹配。"""
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

        seen: set[str] = set()
        unique: list[str] = []
        for t in tags:
            if t and t not in seen:
                seen.add(t)
                unique.append(t)
        return unique
