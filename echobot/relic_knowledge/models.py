from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import RelicBase


class Relic(RelicBase):
    __tablename__ = "relics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    dynasty: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    period: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str | None] = mapped_column(String(50), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    story: Mapped[str] = mapped_column(Text, nullable=False)
    life_insight: Mapped[str | None] = mapped_column(Text)
    emotion_tags: Mapped[list] = mapped_column(JSONB, default=list)
    image_url: Mapped[str | None] = mapped_column(String(512))
    embedding = mapped_column(Vector(1024))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "dynasty": self.dynasty,
            "period": self.period,
            "category": self.category,
            "description": self.description,
            "story": self.story,
            "life_insight": self.life_insight,
            "emotion_tags": self.emotion_tags or [],
            "image_url": self.image_url,
        }
