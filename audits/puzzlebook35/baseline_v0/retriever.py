"""TF-IDF retrieval + minimal intent-conditioned fit_check.

Deterministic: scikit-learn TfidfVectorizer with random_state n/a (no random
component used) and stable scoring; ties broken by chunk_id ordering.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

RETRIEVAL_TOP_K = 10
DOWNSTREAM_K = 4

YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
NUMBER_RE = re.compile(r"\b\d+\b")
NAME_RE = re.compile(
    r"\b[А-ЯA-Z][а-яa-zё]+(?:[\s\-][А-ЯA-Z][а-яa-zё]+)?\b"
)


@dataclass
class Chunk:
    chunk_id: str
    content: str


def load_chunks(path: Path) -> list[Chunk]:
    out: list[Chunk] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            out.append(Chunk(chunk_id=d["chunk_id"], content=d["content"]))
    return out


def build_index(chunks: list[Chunk]) -> tuple[TfidfVectorizer, np.ndarray]:
    docs = [c.content for c in chunks]
    vec = TfidfVectorizer(
        lowercase=True,
        analyzer="word",
        token_pattern=r"(?u)\b\w\w+\b",
        ngram_range=(1, 1),
        norm="l2",
        sublinear_tf=False,
    )
    X = vec.fit_transform(docs)
    return vec, X


def retrieve(
    question: str,
    vec: TfidfVectorizer,
    X,
    chunks: list[Chunk],
    top_k: int = RETRIEVAL_TOP_K,
) -> list[tuple[str, float]]:
    """Return list of (chunk_id, score) sorted by (-score, chunk_id)."""
    q = vec.transform([question])
    sims = cosine_similarity(q, X).ravel()
    pairs = [(chunks[i].chunk_id, float(sims[i])) for i in range(len(chunks))]
    pairs.sort(key=lambda p: (-p[1], p[0]))
    return pairs[:top_k]


def fit_check(
    intent: str,
    topk_chunk_ids: list[str],
    chunks_by_id: dict[str, Chunk],
    downstream_k: int = DOWNSTREAM_K,
) -> tuple[str, str, dict]:
    """Return (fit_status, fit_expected_type, fit_details) per minimal v0 rules.

    Rules (v0):
      intent=when    -> regex YEAR over top-k chunks; >=1 hit -> match else mismatch
      intent=who     -> regex CAPITALIZED NAME; >=2 hits -> match, 1 -> partial, 0 -> mismatch
      intent=how_many-> regex NUMBER; >=1 hit -> match else mismatch
      other          -> skipped
    """
    effective = topk_chunk_ids[:downstream_k]
    joined = "\n".join(chunks_by_id[cid].content for cid in effective if cid in chunks_by_id)

    if intent == "when":
        hits = YEAR_RE.findall(joined)
        status = "match" if len(hits) >= 1 else "mismatch"
        return status, "year", {"year_hits": hits[:10], "downstream_k": downstream_k}

    if intent == "who":
        hits = NAME_RE.findall(joined)
        unique = sorted(set(hits))
        if len(unique) >= 2:
            status = "match"
        elif len(unique) == 1:
            status = "partial"
        else:
            status = "mismatch"
        return status, "person_name", {"name_hits": unique[:10], "downstream_k": downstream_k}

    if intent == "how_many":
        hits = NUMBER_RE.findall(joined)
        status = "match" if len(hits) >= 1 else "mismatch"
        return status, "count", {"number_hits": hits[:10], "downstream_k": downstream_k}

    return "skipped", "n/a", {"reason": f"intent={intent} not handled in v0"}


def final_outcome(fit_status: str, intent: str) -> str:
    if fit_status == "mismatch" and intent in ("when", "who", "how_many"):
        return "fit_refuse"
    return "hit"


def stop_reason(fit_status: str, intent: str, outcome: str) -> str:
    if outcome == "fit_refuse":
        return f"fit_check rejected top-k for intent={intent} (status={fit_status})"
    if fit_status == "skipped":
        return "fit_check skipped (intent not handled in baseline v0); top-k returned as material"
    return f"fit_check status={fit_status} for intent={intent}; top-k returned as material"
