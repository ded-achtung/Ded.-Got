"""Probe D: run the q9_pilot extractor stack on the real puzzlebook35 corpus.

The pilot was built on synthetic Q9 stubs and three real Q4 chunks from a
test-retest archive. The extractors are English-only regex tuned to specific
phrasings ('we implemented N special methods', 'list made of N cards', etc.).

The puzzlebook35 corpus is 27 Russian-language chunks from Whiteside's
'Python в задачах и упражнениях'. Questions in that corpus are mostly intent
'what'; only Q5 and Q14 are 'how_many'.

This probe answers two empirical questions, no architectural change:

  D1: When we point extract_claims / extract_claims_extended at all 27 real
      chunks, how many claims come out? Of what types?

  D2: For the two how_many questions (Q5, Q14), what does retrieve() pick
      from the real corpus, and what does run_primary do end-to-end?
"""

from __future__ import annotations

import json
from pathlib import Path

from claims import extract_claims
from claims_extended import extract_claims_extended
from pilot import retrieve, run_primary

ROOT = Path("/home/user/Ded.-Got/audits/puzzlebook35")
CHUNKS_PATH = ROOT / "audit_v0.chunks.jsonl"
QUESTIONS_PATH = ROOT / "audit_v0.questions.jsonl"


def load_chunks() -> dict[str, dict]:
    """Map puzzlebook chunk schema -> q9_pilot chunk schema.

    puzzlebook chunk: {chunk_id, source, section, page, type, content}
    q9_pilot chunk:   {text, kind?, section?}

    `type: code` -> `kind: code` (so _code_literal can fire).
    """
    out = {}
    with CHUNKS_PATH.open() as f:
        for line in f:
            row = json.loads(line)
            out[row["chunk_id"]] = {
                "text": row["content"],
                "kind": "code" if row.get("type") == "code" else "prose",
                "section": row.get("section", ""),
                "page": row.get("page", ""),
            }
    return out


def load_questions() -> list[dict]:
    rows = []
    with QUESTIONS_PATH.open() as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def d1_extract_all(chunks: dict[str, dict]) -> dict:
    """Run both extractors on every chunk, count what comes out."""
    base_claims = []
    extended_claims = []
    for cid, chunk in chunks.items():
        for c in extract_claims(cid, chunk):
            base_claims.append(c)
        for c in extract_claims_extended(cid, chunk):
            extended_claims.append(c)

    def _by_type(claims):
        out = {}
        for c in claims:
            out[c["source_type"]] = out.get(c["source_type"], 0) + 1
        return out

    return {
        "n_chunks": len(chunks),
        "n_code_chunks": sum(1 for c in chunks.values() if c["kind"] == "code"),
        "extract_claims": {
            "total": len(base_claims),
            "by_type": _by_type(base_claims),
            "samples": [
                {
                    "chunk_id": c["chunk_id"],
                    "type": c["source_type"],
                    "value": c["value"],
                    "evidence": c.get("evidence", "")[:80],
                }
                for c in base_claims[:5]
            ],
        },
        "extract_claims_extended": {
            "total": len(extended_claims),
            "by_type": _by_type(extended_claims),
            "samples": [
                {
                    "chunk_id": c["chunk_id"],
                    "type": c["source_type"],
                    "value": c["value"],
                    "evidence": c.get("evidence", "")[:80],
                }
                for c in extended_claims[:5]
            ],
        },
    }


def d2_run_how_many_questions(chunks: dict[str, dict],
                              questions: list[dict]) -> list[dict]:
    """For each how_many question, retrieve top-4 + run extended pilot."""
    results = []
    for q in questions:
        if q.get("intent") != "how_many":
            continue
        # Naive query: use the question itself; pilot's retrieve() lower-cases
        # and word-overlaps anyway. No translation, no Russian-aware tokens —
        # this is what the system would do today.
        query = q["question"]
        retrieved = retrieve(query, chunks, top_k=4)
        state, winner = run_primary(
            question=q["question"],
            query=query,
            chunks=chunks,
            extractor=extract_claims_extended,
        )
        results.append({
            "qid": q["qid"],
            "question": q["question"],
            "retrieved_top4": [cid for cid, _ in retrieved],
            "K_size": len(state.K),
            "claim_types": sorted({c["source_type"] for c in state.K.values()}),
            "E": state.E,
            "answer": None if winner is None else winner.value,
            "answer_source": None if winner is None else winner.source_type,
            "trace_tail": state.trace[-1] if state.trace else None,
        })
    return results


if __name__ == "__main__":
    chunks = load_chunks()
    questions = load_questions()

    print("=== D1: extractor harvest on real corpus ===")
    print(json.dumps(d1_extract_all(chunks), ensure_ascii=False, indent=2))
    print()

    print("=== D2: how_many questions end-to-end ===")
    for r in d2_run_how_many_questions(chunks, questions):
        print(json.dumps(r, ensure_ascii=False, indent=2))
        print("-" * 60)
