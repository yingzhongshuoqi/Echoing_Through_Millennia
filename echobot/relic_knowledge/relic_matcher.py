from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from .emotion_models import EmotionResult
from .retriever import RelicMatch, RelicRetriever

logger = logging.getLogger(__name__)


class RelicMatcher:
    """Match emotions to historical relics using semantic search + keyword filtering."""

    def __init__(self, retriever: RelicRetriever) -> None:
        self._retriever = retriever

    async def match(
        self,
        db: AsyncSession,
        emotion: EmotionResult,
        used_relic_ids: Sequence[int] | None = None,
    ) -> RelicMatch | None:
        query_text = self._build_query(emotion)
        matches = await self._retriever.search_by_emotion(
            db,
            query_text=query_text,
            keywords=emotion.keywords,
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
        parts = [emotion.primary]
        if emotion.secondary:
            parts.append(emotion.secondary)
        if emotion.need:
            parts.append(emotion.need)
        parts.extend(emotion.keywords[:3])
        return " ".join(parts)
