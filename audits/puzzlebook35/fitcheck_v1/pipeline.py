"""Re-score existing run JSONLs (v0 TF-IDF and v1 BM25) through fit_check v1.

Reads:
  audits/puzzlebook35/runs/<DATE>_v0_baseline.jsonl
  audits/puzzlebook35/runs/<DATE>_v1_bm25.jsonl
  audits/puzzlebook35/corpus/puzzlebook_raw_chunks_v1.jsonl

Writes:
  audits/puzzlebook35/runs/<DATE>_v0_fitchk1.jsonl   (TF-IDF retrieval × v1 fit_check)
  audits/puzzlebook35/runs/<DATE>_v1_fitchk1.jsonl   (BM25  retrieval × v1 fit_check)
  audits/puzzlebook35/manifests/<DATE>_v0_fitchk1.manifest.json
  audits/puzzlebook35/manifests/<DATE>_v1_fitchk1.manifest.json

Retrieval is unchanged — only fit_check, final_outcome, stop_reason fields
are recomputed. retrieved_topk_chunk_ids and retrieval_scores are preserved.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))

from fitcheck_v1 import (  # noqa: E402
    DEFAULT_DOWNSTREAM_K,
    fit_check,
    final_outcome,
    stop_reason,
)

CORPUS_PATH = REPO / "audits/puzzlebook35/corpus/puzzlebook_raw_chunks_v1.jsonl"
RUNS_DIR = REPO / "audits/puzzlebook35/runs"
MANIFESTS_DIR = REPO / "audits/puzzlebook35/manifests"
QUESTIONS_PATH = REPO / "audits/puzzlebook35/audit_v0.questions.jsonl"

INPUT_RUNS = [
    ("v0_baseline", "v0_fitchk1"),
    ("v1_bm25", "v1_fitchk1"),
]


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for blk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(blk)
    return h.hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()]


def load_chunks_by_id(path: Path) -> dict[str, dict]:
    return {c["chunk_id"]: c for c in load_jsonl(path)}


def rescore_run(
    in_path: Path, out_path: Path, run_id: str, chunks_by_id: dict
) -> tuple[dict, dict]:
    rows_in = load_jsonl(in_path)
    outcomes: dict[str, int] = {"hit": 0, "fit_refuse": 0, "given_up": 0}
    fit_dist: dict[str, int] = {"match": 0, "mismatch": 0, "partial": 0, "skipped": 0}

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows_in:
            qid = r["qid"]
            question = r["question"]
            intent = r.get("intent", "what")
            topk = r["retrieved_topk_chunk_ids"]

            fit_status, fit_expected, fit_details = fit_check(
                intent, question, topk, chunks_by_id,
                downstream_k=r.get("downstream_effective_k", DEFAULT_DOWNSTREAM_K),
            )
            outcome = final_outcome(fit_status, intent)
            stop = stop_reason(fit_status, intent, outcome, fit_details)
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
            fit_dist[fit_status] = fit_dist.get(fit_status, 0) + 1

            new_row = {
                **r,
                "run_id": run_id,
                "fit_status": fit_status,
                "fit_expected_type": fit_expected,
                "fit_details": fit_details,
                "final_outcome": outcome,
                "stop_reason": stop,
            }
            f.write(json.dumps(new_row, ensure_ascii=False, sort_keys=True) + "\n")
    return outcomes, fit_dist


def write_manifest(
    manifest_path: Path,
    run_id: str,
    run_date: str,
    in_path: Path,
    out_path: Path,
    questions_count: int,
    outcomes: dict,
    fit_dist: dict,
    upstream_label: str,
) -> None:
    manifest = {
        "run_id": run_id,
        "run_date": run_date,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "simulated": False,
        "what_is_real_vs_constructed": {
            "corpus_pages": "REAL (inherited)",
            "chunk_content": "REAL — direct PDF extraction (inherited)",
            "chunk_ids_and_boundaries": "DETERMINISTIC (inherited)",
            "questions": "INHERITED from puzzlebook35 audit_v0.questions.jsonl",
            "runtime_metrics_jsonl": f"REAL — {upstream_label} retrieval × fit_check v1",
            "audit_labels": "n/a — no audit rows produced here",
        },
        "upstream_run": {
            "label": upstream_label,
            "path": str(in_path.relative_to(REPO)),
            "sha256": file_sha256(in_path),
        },
        "corpus": {
            "chunks_path": str(CORPUS_PATH.relative_to(REPO)),
            "chunks_sha256": file_sha256(CORPUS_PATH),
        },
        "questions_source": {
            "path": str(QUESTIONS_PATH.relative_to(REPO)),
            "sha256": file_sha256(QUESTIONS_PATH),
            "count": questions_count,
        },
        "fit_check": {
            "version": "v1_hybrid",
            "design_doc": "audits/puzzlebook35/baseline_v0/FITCHECK_V1_DESIGN.md",
            "approach": "trigger_windows (A) + alignment_floor + section_path_gate (minimal B)",
            "downstream_effective_k": DEFAULT_DOWNSTREAM_K,
            "intents_handled": ["when", "who", "how_many", "what", "why", "how"],
        },
        "experiment": {
            "fixed": "retrieval (inherited from upstream_run); chunks; questions; fit_check downstream_k",
            "changed": "fit_check policy (v0 bare regex → v1 hybrid)",
        },
        "run": {
            "path": str(out_path.relative_to(REPO)),
            "sha256": file_sha256(out_path),
            "row_count": questions_count,
            "outcomes": outcomes,
            "fit_status_distribution": fit_dist,
        },
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-date", default=dt.date.today().isoformat())
    args = ap.parse_args()
    run_date = args.run_date

    chunks_by_id = load_chunks_by_id(CORPUS_PATH)

    summaries = {}
    for upstream_short, out_short in INPUT_RUNS:
        in_path = RUNS_DIR / f"{run_date}_{upstream_short}.jsonl"
        if not in_path.exists():
            print(f"WARN: upstream run missing: {in_path}", file=sys.stderr)
            continue
        run_id = f"{run_date}_{out_short}"
        out_path = RUNS_DIR / f"{run_id}.jsonl"
        manifest_path = MANIFESTS_DIR / f"{run_id}.manifest.json"

        outcomes, fit_dist = rescore_run(in_path, out_path, run_id, chunks_by_id)
        write_manifest(
            manifest_path, run_id, run_date, in_path, out_path,
            questions_count=len(load_jsonl(in_path)),
            outcomes=outcomes,
            fit_dist=fit_dist,
            upstream_label=upstream_short,
        )
        summaries[run_id] = {"outcomes": outcomes, "fit_dist": fit_dist}

    print(f"Re-scored {len(summaries)} runs through fit_check v1:")
    for run_id, s in summaries.items():
        o = s["outcomes"]; fd = s["fit_dist"]
        print(f"  {run_id}:")
        print(f"    outcomes: hit={o.get('hit',0)}  fit_refuse={o.get('fit_refuse',0)}  given_up={o.get('given_up',0)}")
        print(f"    fit_dist: match={fd.get('match',0)}  partial={fd.get('partial',0)}  mismatch={fd.get('mismatch',0)}  skipped={fd.get('skipped',0)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
