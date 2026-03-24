from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .embeddings import EmbeddingService
from .models import Relic

logger = logging.getLogger(__name__)


@dataclass
class RelicMatch:
    relic: Relic
    score: float
    match_reason: str = ""

    def to_dict(self) -> dict:
        return {
            **self.relic.to_dict(),
            "score": round(self.score, 4),
            "match_reason": self.match_reason,
        }


class RelicRetriever:
    """Retrieve relics from knowledge base using pgvector semantic search."""

    def __init__(self, embedding_service: EmbeddingService) -> None:
        self._embedding = embedding_service

    @staticmethod
    def _row_to_relic(row) -> Relic:
        ev = getattr(row, "emotion_vector", None)
        return Relic(
            id=row.id, name=row.name, dynasty=row.dynasty,
            period=row.period, category=row.category,
            description=row.description, story=row.story,
            life_insight=row.life_insight, emotion_tags=row.emotion_tags or [],
            image_url=row.image_url, created_at=row.created_at,
            emotion_vector=list(ev) if ev is not None else None,
        )

    async def search_by_emotion(
        self,
        db: AsyncSession,
        query_text: str,
        keywords: list[str] | None = None,
        emotion_vector: list[float] | None = None,
        limit: int = 3,
    ) -> list[RelicMatch]:
        query_embedding = await self._embedding.embed(query_text)

        if emotion_vector and len(emotion_vector) == 8:
            results = await self._hybrid_search(
                db, query_embedding, emotion_vector, limit=limit * 2,
            )
        else:
            results = await self._vector_search(db, query_embedding, limit=limit * 2)

        if keywords:
            keyword_results = await self._keyword_search(
                db, keywords, emotion_vector=emotion_vector, limit=limit,
            )
            seen_ids = {r.relic.id for r in results}
            for kr in keyword_results:
                if kr.relic.id not in seen_ids:
                    results.append(kr)

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    async def search_by_text(
        self,
        db: AsyncSession,
        query_text: str,
        limit: int = 5,
    ) -> list[RelicMatch]:
        query_embedding = await self._embedding.embed(query_text)
        return await self._vector_search(db, query_embedding, limit=limit)

    async def _vector_search(
        self,
        db: AsyncSession,
        embedding: list[float],
        limit: int = 5,
    ) -> list[RelicMatch]:
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
        query = text(
            """
            SELECT id, name, dynasty, period, category, description, story,
                   life_insight, emotion_tags, image_url, created_at,
                   emotion_vector,
                   1 - (embedding <=> CAST(:embedding AS vector)) as similarity
            FROM relics
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
            """
        )
        result = await db.execute(query, {"embedding": embedding_str, "limit": limit})
        rows = result.fetchall()

        matches = []
        for row in rows:
            relic = self._row_to_relic(row)
            matches.append(RelicMatch(relic=relic, score=float(row.similarity), match_reason="semantic"))
        return matches

    async def _hybrid_search(
        self,
        db: AsyncSession,
        embedding: list[float],
        emotion_vector: list[float],
        limit: int = 5,
        semantic_weight: float = 0.5,
    ) -> list[RelicMatch]:
        """1024-dim semantic + 8-dim Plutchik emotion vector, equal weight by default."""
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
        emo_str = "[" + ",".join(str(x) for x in emotion_vector) + "]"
        emo_weight = 1.0 - semantic_weight
        query = text(
            """
            SELECT id, name, dynasty, period, category, description, story,
                   life_insight, emotion_tags, image_url, created_at,
                   emotion_vector,
                   1 - (embedding <=> CAST(:embedding AS vector)) AS semantic_sim,
                   COALESCE(1 - (emotion_vector <=> CAST(:emo_vec AS vector(8))), 0) AS emotion_sim,
                   :sw * (1 - (embedding <=> CAST(:embedding AS vector)))
                   + :ew * COALESCE(1 - (emotion_vector <=> CAST(:emo_vec AS vector(8))), 0)
                   AS combined_score
            FROM relics
            WHERE embedding IS NOT NULL
            ORDER BY combined_score DESC
            LIMIT :limit
            """
        )
        result = await db.execute(query, {
            "embedding": embedding_str,
            "emo_vec": emo_str,
            "sw": semantic_weight,
            "ew": emo_weight,
            "limit": limit,
        })
        rows = result.fetchall()

        matches = []
        for row in rows:
            relic = self._row_to_relic(row)
            matches.append(RelicMatch(
                relic=relic,
                score=float(row.combined_score),
                match_reason=f"hybrid(sem={row.semantic_sim:.3f},emo={row.emotion_sim:.3f})",
            ))
        return matches

    async def _keyword_search(
        self,
        db: AsyncSession,
        keywords: list[str],
        emotion_vector: list[float] | None = None,
        limit: int = 3,
    ) -> list[RelicMatch]:
        if not keywords:
            return []

        conditions = []
        params: dict = {}
        for i, kw in enumerate(keywords[:5]):
            param_name = f"kw_{i}"
            conditions.append(f"emotion_tags @> CAST(:{param_name} AS jsonb)")
            params[param_name] = f'["{kw}"]'

        where_clause = " OR ".join(conditions)

        if emotion_vector and len(emotion_vector) == 8:
            emo_str = "[" + ",".join(str(x) for x in emotion_vector) + "]"
            sql = (
                f"SELECT *, "
                f"COALESCE(1 - (emotion_vector <=> CAST(:emo_vec AS vector(8))), 0.5) AS kw_score "
                f"FROM relics WHERE {where_clause} "
                f"ORDER BY kw_score DESC LIMIT :limit"
            )
            params["emo_vec"] = emo_str
        else:
            sql = f"SELECT *, 0.5 AS kw_score FROM relics WHERE {where_clause} LIMIT :limit"

        params["limit"] = limit
        result = await db.execute(text(sql), params)
        rows = result.fetchall()

        matches = []
        for row in rows:
            relic = self._row_to_relic(row)
            matches.append(RelicMatch(
                relic=relic,
                score=float(row.kw_score),
                match_reason="keyword",
            ))
        return matches

    async def get_random(self, db: AsyncSession, limit: int = 1) -> list[RelicMatch]:
        result = await db.execute(
            text("SELECT * FROM relics ORDER BY RANDOM() LIMIT :limit"),
            {"limit": limit},
        )
        rows = result.fetchall()
        return [
            RelicMatch(relic=self._row_to_relic(row), score=1.0, match_reason="random")
            for row in rows
        ]
