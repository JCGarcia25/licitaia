"""Embeddings con proveedor configurable.

- 'fake' (por defecto): hashing determinista de bolsas de palabras — funciona sin
  claves externas, es reproducible y suficiente para pruebas/desarrollo.
- 'openai': usa text-embedding-3-small si hay clave (producción).

En producción con PostgreSQL se recomienda pgvector; aquí el vector vive como JSON
y la similitud se calcula con coseno (ver docs/decisiones-arquitectonicas.md, ADR-004).
"""
from __future__ import annotations

import hashlib
import math
import re

from app.core.config import get_settings

_TOKEN = re.compile(r"[a-záéíóúñü0-9]{3,}", re.IGNORECASE)
_STOPWORDS = {
    "de", "la", "el", "los", "las", "del", "para", "por", "con", "que", "y", "en", "a",
    "un", "una", "es", "ser", "sobre", "como", "sus", "su", "al", "se", "no", "lo",
}


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text or "") if t.lower() not in _STOPWORDS]


def _fake_embed(text: str, dim: int) -> list[float]:
    vec = [0.0] * dim
    for tok in tokenize(text):
        h = hashlib.blake2b(tok.encode(), digest_size=8).digest()
        idx = int.from_bytes(h[:4], "big") % dim
        sign = 1.0 if h[4] % 2 else -1.0
        vec[idx] += sign * (1.0 + (h[5] % 10) / 10.0)
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [round(v / norm, 6) for v in vec]


def _openai_embed(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI  # importación diferida: dependencia opcional

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.embeddings.create(model="text-embedding-3-small", input=texts)
    return [d.embedding for d in resp.data]


def embed(text: str) -> list[float]:
    """Devuelve un vector normalizado para el texto dado."""
    settings = get_settings()
    if settings.embedding_provider == "openai" and settings.openai_api_key:
        return _openai_embed([text])[0]
    return _fake_embed(text, settings.embedding_dim)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return max(0.0, min(1.0, dot / (na * nb)))


def lexical_overlap(query: str, text: str) -> list[str]:
    """Palabras compartidas — se usan como razones verificables del matching."""
    qt = set(tokenize(query))
    tt = set(tokenize(text))
    return sorted(qt & tt)[:12]
