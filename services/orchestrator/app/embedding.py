"""Deterministic, offline embeddings for the Week 8 retrieval baseline.

This is an engineering baseline, not a clinically validated semantic model. The provider name
and dimensions are part of the frozen corpus contract so a production embedding model can replace
it without silently mixing incompatible vectors.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable

PROVIDER = "clinical-hash-embedding-v1"
DIMENSIONS = 256

_ALIASES = (
    (r"non[- ]small cell lung cancer", "nsclc"),
    (r"epidermal growth factor receptor", "egfr"),
    (r"anaplastic lymphoma kinase", "alk"),
    (r"programmed death[- ]ligand 1", "pdl1"),
    (r"pd[- ]l1", "pdl1"),
    (r"mesenchymal epithelial transition", "met"),
    (r"human epidermal growth factor receptor 2", "her2"),
    (r"erbb2", "her2"),
    (r"functional status", "performance status"),
    (r"intracranial", "brain"),
    (r"tyrosine kinase inhibitor", "tki"),
    (r"resection|resected", "surgery"),
)
_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


def normalize_text(text: str) -> str:
    normalized = text.lower()
    for pattern, replacement in _ALIASES:
        normalized = re.sub(pattern, replacement, normalized)
    return normalized


def lexical_tokens(text: str) -> list[str]:
    return [
        token
        for token in _TOKEN.findall(normalize_text(text))
        if token not in _STOPWORDS and len(token) > 1
    ]


def _features(tokens: list[str]) -> Iterable[str]:
    yield from tokens
    yield from (f"{left}_{right}" for left, right in zip(tokens, tokens[1:], strict=False))


def embed(text: str) -> list[float]:
    """Return a stable signed feature-hash vector with L2 normalization."""

    vector = [0.0] * DIMENSIONS
    for feature in _features(lexical_tokens(text)):
        digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
        raw = int.from_bytes(digest)
        vector[raw % DIMENSIONS] += 1.0 if raw & 1 else -1.0

    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("vectors must have the same dimensions")
    return sum(a * b for a, b in zip(left, right, strict=True))
