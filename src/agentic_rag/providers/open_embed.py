"""Real OpenAI-compatible embedding interface; remote provider for production."""

from __future__ import annotations

import math
from urllib.parse import urlsplit

import httpx


class OpenAIEmbed:
    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("Embedding provider requires API key")
        parsed = urlsplit(base_url)
        if (
            (
                parsed.scheme != "https"
                and not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"})
            )
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            raise ValueError(
                "Embedding endpoint must use HTTPS or loopback without URL credentials"
            )
        self.model = model
        self.api_key = api_key
        self.url = base_url.rstrip("/") + "/embeddings"
        self.client = client or httpx.AsyncClient(timeout=30)
        self._owns_client = client is None

    async def documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = await self.client.post(
            self.url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": texts},
        )
        response.raise_for_status()
        data = sorted(response.json()["data"], key=lambda item: item["index"])
        if len(data) != len(texts):
            raise ValueError("Embedding response count mismatch")
        vectors = [item["embedding"] for item in data]
        sizes = {len(vector) for vector in vectors if isinstance(vector, list)}
        if (
            len(sizes) != 1
            or not sizes.pop()
            or any(
                not isinstance(n, (int, float)) or not math.isfinite(n)
                for vector in vectors
                for n in vector
            )
        ):
            raise ValueError("Malformed embedding dimensions or values")
        return vectors

    async def query(self, text: str) -> list[float]:
        return (await self.documents([text]))[0]

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()
