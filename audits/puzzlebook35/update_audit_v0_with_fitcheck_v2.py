"""Idempotent: extend `raw_corpus_confirmation.outcomes_grid` of each
audit row with two v2 cells (TF-IDF×v2, BM25×v2). Reads the empirical
v2 outcomes from the actual run JSONLs, so the script stays correct
across reruns.

Backward-compatible: if outcomes_grid already has the v2 cells with
matching content, no change.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIT_PATH = HERE / "audit_v0.manual.jsonl"
RUNS_DIR = HERE / "runs"

QIDS = ("Q2", "Q7", "Q22")


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.open(encoding="utf-8") if l.strip()]


def load_run_by_qid(name: str) -> dict[str, dict]:
    candidates = sorted(RUNS_DIR.glob(f"*_{name}.jsonl"))
    if not candidates:
        raise FileNotFoundError(f"No *_{name}.jsonl under {RUNS_DIR}")
    return {r["qid"]: r for r in load_jsonl(candidates[-1])}


def cell(row: dict) -> dict:
    return {
        "fit_status": row["fit_status"],
        "final_outcome": row["final_outcome"],
        "top1_chunk_id": row["retrieved_topk_chunk_ids"][0]
            if row["retrieved_topk_chunk_ids"] else None,
    }


def main() -> int:
    if not AUDIT_PATH.exists():
        print(f"missing: {AUDIT_PATH}", file=sys.stderr)
        return 1

    v0_fc2 = load_run_by_qid("v0_fitchk2")
    v1_fc2 = load_run_by_qid("v1_fitchk2")

    rows = load_jsonl(AUDIT_PATH)

    changed = 0
    for r in rows:
        qid = r["qid"]
        if qid not in QIDS:
            continue
        rcc = r.get("raw_corpus_confirmation")
        if not rcc:
            continue
        grid = rcc.setdefault("outcomes_grid", {})
        new_v0 = cell(v0_fc2[qid])
        new_v1 = cell(v1_fc2[qid])
        existing_v0 = grid.get("v0_tfidf_x_fitcheck_v2_per_intent_floor")
        existing_v1 = grid.get("v1_bm25_x_fitcheck_v2_per_intent_floor")
        if existing_v0 == new_v0 and existing_v1 == new_v1:
            continue
        grid["v0_tfidf_x_fitcheck_v2_per_intent_floor"] = new_v0
        grid["v1_bm25_x_fitcheck_v2_per_intent_floor"]   = new_v1
        # also stamp the v2 evidence path
        ep = rcc.setdefault("evidence_paths", [])
        v2_paths = [
            "audits/puzzlebook35/baseline_v0/FITCHECK_V2_DESIGN.md",
            "audits/puzzlebook35/fitcheck_v2/COMPARE_v1_v2_fitcheck.md",
        ]
        for p in v2_paths:
            if p not in ep:
                ep.append(p)
        changed += 1

    with AUDIT_PATH.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Extended {changed} of {len(rows)} rows with v2 outcomes_grid cells.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
