"""Probe G2: compare three retrievers on the two how_many questions.

Question: does retrieve choice change which chunk lands in top-K? D2 showed
pilot's naive keyword overlap already finds pb_t01_001 for Q14 (where the
literal answer 'один параметр' lives). G2 checks whether TF-IDF and BM25
do strictly better, equal, or different.

Three retrievers, all reading from audit_v0.chunks.jsonl:

  R1 - pilot keyword overlap (pilot.retrieve, the in-tree default)
  R2 - TF-IDF cosine        (ported from baseline_v0/retriever.py on PR #4)
  R3 - BM25 Okapi           (ported from baseline_v1_bm25/retriever_bm25.py)

R2/R3 ports are inline because the baseline code lives on a different branch.
Tokenization for R2/R3 follows the PR #4 originals: lowercase + r'\\b\\w\\w+\\b'.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi

from pilot import retrieve as pilot_retrieve

ROOT = Path("/home/user/Ded.-Got/audits/puzzlebook35")
CHUNKS_PATH = ROOT / "audit_v0.chunks.jsonl"
QUESTIONS_PATH = ROOT / "audit_v0.questions.jsonl"

TOKEN_RE = re.compile(r"(?u)\b\w\w+\b")
TOP_K = 4


def load_chunks_full() -> list[dict]:
    with CHUNKS_PATH.open() as f:
        return [json.loads(line) for line in f]


def load_questions() -> list[dict]:
    with QUESTIONS_PATH.open() as f:
        return [json.loads(line) for line in f]


def to_pilot_chunks(rows: list[dict]) -> dict[str, dict]:
    return {
        r["chunk_id"]: {
            "text": r["content"],
            "kind": "code" if r.get("type") == "code" else "prose",
            "section": r.get("section", ""),
        }
        for r in rows
    }


def r1_pilot(question: str, rows: list[dict]) -> list[tuple[str, int]]:
    pilot_chunks = to_pilot_chunks(rows)
    hits = pilot_retrieve(question, pilot_chunks, top_k=TOP_K)
    # pilot.retrieve returns [(cid, chunk_dict)]; rebuild score from _score()
    from pilot import _score
    return [(cid, _score(question, pilot_chunks[cid])) for cid, _ in hits]


def r2_tfidf(question: str, rows: list[dict]) -> list[tuple[str, float]]:
    docs = [r["content"] for r in rows]
    vec = TfidfVectorizer(
        lowercase=True,
        analyzer="word",
        token_pattern=r"(?u)\b\w\w+\b",
        ngram_range=(1, 1),
        norm="l2",
        sublinear_tf=False,
    )
    X = vec.fit_transform(docs)
    q = vec.transform([question])
    sims = cosine_similarity(q, X).ravel()
    pairs = [(rows[i]["chunk_id"], float(sims[i])) for i in range(len(rows))]
    pairs.sort(key=lambda p: (-p[1], p[0]))
    return pairs[:TOP_K]


def r3_bm25(question: str, rows: list[dict]) -> list[tuple[str, float]]:
    def tok(t: str) -> list[str]:
        return TOKEN_RE.findall(t.lower())
    bm25 = BM25Okapi([tok(r["content"]) for r in rows])
    scores = bm25.get_scores(tok(question))
    pairs = [(rows[i]["chunk_id"], float(scores[i])) for i in range(len(rows))]
    pairs.sort(key=lambda p: (-p[1], p[0]))
    return pairs[:TOP_K]


def _fmt(pairs):
    return [(cid, round(score, 3)) for cid, score in pairs]


def compare(question: str, rows: list[dict]) -> dict:
    return {
        "question": question,
        "R1_pilot_overlap": _fmt(r1_pilot(question, rows)),
        "R2_tfidf":         _fmt(r2_tfidf(question, rows)),
        "R3_bm25":          _fmt(r3_bm25(question, rows)),
    }


def overlap_stats(a: list[tuple], b: list[tuple]) -> dict:
    """Set + ordered overlap between two top-K lists."""
    ids_a = [cid for cid, _ in a]
    ids_b = [cid for cid, _ in b]
    set_overlap = len(set(ids_a) & set(ids_b))
    rank_match = sum(1 for i in range(min(len(ids_a), len(ids_b))) if ids_a[i] == ids_b[i])
    return {"set_overlap": set_overlap, "rank_match": rank_match}


if __name__ == "__main__":
    rows = load_chunks_full()
    questions = load_questions()

    targets = [q for q in questions if q.get("intent") == "how_many"]
    print(f"# {len(rows)} chunks loaded; {len(targets)} how_many questions")
    print()

    for q in targets:
        result = compare(q["question"], rows)
        print(f"=== {q['qid']}: {q['question']} ===")
        for key in ("R1_pilot_overlap", "R2_tfidf", "R3_bm25"):
            print(f"  {key}: {result[key]}")
        # Pairwise top-K overlap.
        ovs = {
            "R1_vs_R2": overlap_stats(result["R1_pilot_overlap"], result["R2_tfidf"]),
            "R2_vs_R3": overlap_stats(result["R2_tfidf"], result["R3_bm25"]),
            "R1_vs_R3": overlap_stats(result["R1_pilot_overlap"], result["R3_bm25"]),
        }
        print(f"  overlap: {json.dumps(ovs, ensure_ascii=False)}")
        print()
