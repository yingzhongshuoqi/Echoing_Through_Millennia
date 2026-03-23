from __future__ import annotations

import logging
import os
from typing import Any

from ...relic_knowledge import db as relic_db_module
from ...relic_knowledge.db import get_relic_db_session
from ...relic_knowledge.embeddings import EmbeddingService
from ...relic_knowledge.retriever import RelicRetriever, RelicMatch
from ...relic_knowledge.models import Relic

from sqlalchemy import select, func, text

logger = logging.getLogger(__name__)


class RelicService:
    """Service layer for relic knowledge base CRUD and search."""

    def __init__(self) -> None:
        self._retriever: RelicRetriever | None = None

    def _get_retriever(self) -> RelicRetriever | None:
        if self._retriever is not None:
            return self._retriever

        api_key = os.environ.get("EMBEDDING_API_KEY", "").strip()
        if not api_key:
            return None

        embedding_service = EmbeddingService(
            api_key=api_key,
            base_url=os.environ.get(
                "EMBEDDING_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ).strip(),
            model=os.environ.get("EMBEDDING_MODEL", "text-embedding-v3").strip(),
            dimensions=int(os.environ.get("EMBEDDING_DIMENSIONS", "1024")),
        )
        self._retriever = RelicRetriever(embedding_service)
        return self._retriever

    @property
    def available(self) -> bool:
        return relic_db_module._engine is not None

    async def list_relics(
        self,
        dynasty: str | None = None,
        category: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> dict[str, Any]:
        async with get_relic_db_session() as db:
            query = select(Relic)
            count_query = select(func.count(Relic.id))
            if dynasty:
                query = query.where(Relic.dynasty == dynasty)
                count_query = count_query.where(Relic.dynasty == dynasty)
            if category:
                query = query.where(Relic.category == category)
                count_query = count_query.where(Relic.category == category)

            total_result = await db.execute(count_query)
            total = total_result.scalar() or 0

            query = query.offset(offset).limit(limit).order_by(Relic.id)
            result = await db.execute(query)
            relics = result.scalars().all()

            return {
                "total": total,
                "offset": offset,
                "limit": limit,
                "items": [r.to_dict() for r in relics],
            }

    async def get_relic(self, relic_id: int) -> dict | None:
        async with get_relic_db_session() as db:
            result = await db.execute(select(Relic).where(Relic.id == relic_id))
            relic = result.scalar_one_or_none()
            return relic.to_dict() if relic else None

    async def get_random(self, limit: int = 1) -> list[dict]:
        retriever = self._get_retriever()
        if retriever is None:
            return []
        async with get_relic_db_session() as db:
            matches = await retriever.get_random(db, limit=limit)
            return [m.to_dict() for m in matches]

    async def search(self, query: str, limit: int = 5) -> list[dict]:
        retriever = self._get_retriever()
        if retriever is None:
            return []
        async with get_relic_db_session() as db:
            matches = await retriever.search_by_text(db, query, limit=limit)
            return [m.to_dict() for m in matches]
