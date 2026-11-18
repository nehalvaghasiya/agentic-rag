"""Deterministic token-hashing embedding: test-only, not a semantic model."""

from __future__ import annotations

import hashlib
import math
import re


class HashEmbed:
    """Stable sparse token hash to make offline retrieval reproducible."""

    def __init__(self, dimension: int = 256) -> None:
        self.dimension = dimension

    async def query(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for word in re.findall(r"[a-z0-9]+", text.casefold()):
            key = int.from_bytes(hashlib.blake2b(word.encode(), digest_size=8).digest(), "big")
            vector[key % self.dimension] += 1.0
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return [value / norm for value in vector]

    async def documents(self, texts: list[str]) -> list[list[float]]:
        return [await self.query(text) for text in texts]
