from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field

TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_+-]{1,}")


def embed_text(text: str, *, dimensions: int = 384) -> list[float]:
    """Deterministic local embedding fallback for tests and offline indexing.

    Production deployments should swap this adapter for a hosted embedding model and persist
    vectors in pgvector or Qdrant. The interface is intentionally compatible with that path.
    """
    vector = [0.0] * dimensions
    for token in TOKEN_RE.findall(text.lower()):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % dimensions
        sign = -1.0 if digest[4] % 2 else 1.0
        vector[bucket] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Embedding vectors must have the same dimensionality")
    return sum(a * b for a, b in zip(left, right))


@dataclass
class InMemoryVectorIndex:
    dimensions: int = 384
    vectors: dict[str, list[float]] = field(default_factory=dict)
    payloads: dict[str, dict[str, object]] = field(default_factory=dict)

    def upsert(self, key: str, text: str, payload: dict[str, object] | None = None) -> None:
        self.vectors[key] = embed_text(text, dimensions=self.dimensions)
        self.payloads[key] = payload or {}

    def search(self, text: str, *, limit: int = 10) -> list[dict[str, object]]:
        query = embed_text(text, dimensions=self.dimensions)
        scored = [
            {
                "id": key,
                "score": round(max(0.0, cosine_similarity(query, vector)), 6),
                "payload": self.payloads.get(key, {}),
            }
            for key, vector in self.vectors.items()
        ]
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:limit]
