"""Eye-pass over 35 run rows: print qid, question, top-1 chunk excerpt.

Not an audit — a one-shot glance to spot obviously irrelevant top-1
hits before any re-labeling happens.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CHUNKS = REPO / "audits/puzzlebook35/corpus/puzzlebook_raw_chunks_v1.jsonl"
RUNS = sorted((REPO / "audits/puzzlebook35/runs").glob("*_v0_baseline.jsonl"))[-1]


def jsonl(p: Path):
    return [json.loads(l) for l in p.open(encoding="utf-8") if l.strip()]


def main() -> int:
    chunks = {c["chunk_id"]: c for c in jsonl(CHUNKS)}
    rows = jsonl(RUNS)
    for r in rows:
        qid, q, intent, fit, outcome = (
            r["qid"], r["question"], r["intent"], r["fit_status"], r["final_outcome"],
        )
        top1 = r["retrieved_topk_chunk_ids"][0] if r["retrieved_topk_chunk_ids"] else None
        section = "/".join(chunks[top1]["section_path"]) if top1 else "-"
        excerpt = chunks[top1]["content"][:200].replace("\n", " ") if top1 else "-"
        print(f"{qid:>4}  intent={intent:<9} fit={fit:<8} outcome={outcome}")
        print(f"      Q: {q}")
        print(f"      top-1: {top1}  [{section}]")
        print(f"      excerpt: {excerpt}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
