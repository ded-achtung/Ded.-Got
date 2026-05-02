"""BM25 retrieval (Okapi) + reuses fit_check from baseline_v0.

Tokenization is identical to v0 (lowercase + \\b\\w\\w+\\b) so the only
controlled change between v0 and v1 is the scoring formula.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

HERE = Path(__file__).resolve().parent
V0_DIR = HERE.parents[0] / "baseline_v0"
sys.path.insert(0, str(V0_DIR))

from retriever import (  # noqa: E402  (reuse v0 fit_check + dataclass)
    DOWNSTREAM_K,
    RETRIEVAL_TOP_K,
    Chunk,
    fit_check,
    final_outcome,
    load_chunks,
    stop_reason,
)

TOKEN_RE = re.compile(r"(?u)\b\w\w+\b")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def build_bm25(chunks: list[Chunk]) -> BM25Okapi:
    corpus = [tokenize(c.content) for c in chunks]
    return BM25Okapi(corpus)


def retrieve(
    question: str,
    bm25: BM25Okapi,
    chunks: list[Chunk],
    top_k: int = RETRIEVAL_TOP_K,
) -> list[tuple[str, float]]:
    """Return [(chunk_id, score), ...] sorted by (-score, chunk_id)."""
    q_tokens = tokenize(question)
    scores = bm25.get_scores(q_tokens)
    pairs = [(chunks[i].chunk_id, float(scores[i])) for i in range(len(chunks))]
    pairs.sort(key=lambda p: (-p[1], p[0]))
    return pairs[:top_k]


__all__ = [
    "RETRIEVAL_TOP_K",
    "DOWNSTREAM_K",
    "Chunk",
    "build_bm25",
    "retrieve",
    "fit_check",
    "final_outcome",
    "stop_reason",
    "load_chunks",
    "tokenize",
]
