from __future__ import annotations

import asyncio
import json
import logging
from urllib import error, request

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generate text embeddings via OpenAI-compatible API."""

    def __init__(self, api_key: str, base_url: str, model: str, dimensions: int = 1024) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._dimensions = dimensions

    async def embed(self, text: str) -> list[float]:
        return await asyncio.to_thread(self._embed_sync, text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._embed_batch_sync, texts)

    def _embed_sync(self, text: str) -> list[float]:
        result = self._embed_batch_sync([text])
        return result[0] if result else [0.0] * self._dimensions

    def _embed_batch_sync(self, texts: list[str]) -> list[list[float]]:
        payload: dict = {
            "model": self._model,
            "input": texts,
        }
        if self._dimensions:
            payload["dimensions"] = self._dimensions

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        url = f"{self._base_url}/embeddings"
        req = request.Request(
            url=url,
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Embedding API failed: {exc.code}, {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Embedding API network error: {exc.reason}") from exc

        embeddings = []
        for item in sorted(data.get("data", []), key=lambda x: x.get("index", 0)):
            embeddings.append(item["embedding"])
        return embeddings
