"""Baseline v1 pipeline: BM25 over the same raw chunks as v0.

Reuses puzzlebook_raw_chunks_v1.jsonl produced by baseline_v0. Output:
    audits/puzzlebook35/runs/<RUN_DATE>_v1_bm25.jsonl
    audits/puzzlebook35/manifests/<RUN_DATE>_v1_bm25.manifest.json

If the chunks file is missing, falls back to running the v0 extractor
end-to-end so the pipeline is self-contained.
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
V0_DIR = REPO / "audits" / "puzzlebook35" / "baseline_v0"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(V0_DIR))

from retriever_bm25 import (  # noqa: E402
    DOWNSTREAM_K,
    RETRIEVAL_TOP_K,
    build_bm25,
    fit_check,
    final_outcome,
    load_chunks,
    retrieve,
    stop_reason,
)

DEFAULT_PDF = REPO / "Python в задачах и упражнениях.pdf"
QUESTIONS_PATH = REPO / "audits" / "puzzlebook35" / "audit_v0.questions.jsonl"
CORPUS_PATH = REPO / "audits" / "puzzlebook35" / "corpus" / "puzzlebook_raw_chunks_v1.jsonl"
RUNS_DIR = REPO / "audits" / "puzzlebook35" / "runs"
MANIFESTS_DIR = REPO / "audits" / "puzzlebook35" / "manifests"

CORPUS_NAME = "puzzlebook_raw_intro_t1_15"
SOURCE_TAG = "whiteside_puzzlebook_2025_ru"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for blk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(blk)
    return h.hexdigest()


def load_questions(path: Path) -> list[dict]:
    out = []
    with path.open("r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            out.append(json.loads(ln))
    return out


def ensure_chunks(pdf_path: Path) -> None:
    """If chunks.jsonl missing, run v0 extractor to produce it."""
    if CORPUS_PATH.exists():
        return
    sys.path.insert(0, str(V0_DIR))
    from extractor import (  # noqa: E402
        PAGE_FROM,
        PAGE_TO,
        chunk_pages,
        extract_pages,
        write_chunks_jsonl,
    )
    pages = extract_pages(pdf_path, PAGE_FROM, PAGE_TO)
    chunks = chunk_pages(pages)
    write_chunks_jsonl(chunks, CORPUS_PATH)


def run_pipeline(pdf_path: Path, run_date: str) -> dict:
    if not QUESTIONS_PATH.exists():
        raise FileNotFoundError(QUESTIONS_PATH)
    ensure_chunks(pdf_path)

    chunks = load_chunks(CORPUS_PATH)
    if len(chunks) < 25:
        raise RuntimeError(f"chunks.jsonl has {len(chunks)} rows (<25)")
    chunks_by_id = {c.chunk_id: c for c in chunks}

    bm25 = build_bm25(chunks)

    questions = load_questions(QUESTIONS_PATH)
    if len(questions) != 35:
        raise RuntimeError(f"Expected 35 questions, got {len(questions)}")

    run_id = f"{run_date}_v1_bm25"
    runs_path = RUNS_DIR / f"{run_id}.jsonl"
    runs_path.parent.mkdir(parents=True, exist_ok=True)

    outcomes = {"hit": 0, "fit_refuse": 0, "given_up": 0}
    fit_dist = {"match": 0, "mismatch": 0, "partial": 0, "skipped": 0}

    with runs_path.open("w", encoding="utf-8") as f:
        for q in questions:
            qid = q["qid"]
            question = q["question"]
            intent = q.get("intent", "what")
            topk_pairs = retrieve(question, bm25, chunks, top_k=RETRIEVAL_TOP_K)
            topk_ids = [cid for cid, _ in topk_pairs]
            scores = {cid: round(score, 6) for cid, score in topk_pairs}

            fit_status, fit_expected, fit_details = fit_check(
                intent, topk_ids, chunks_by_id, downstream_k=DOWNSTREAM_K
            )
            outcome = final_outcome(fit_status, intent)
            stop = stop_reason(fit_status, intent, outcome)

            outcomes[outcome] = outcomes.get(outcome, 0) + 1
            fit_dist[fit_status] = fit_dist.get(fit_status, 0) + 1

            row = {
                "run_id": run_id,
                "qid": qid,
                "question": question,
                "intent": intent,
                "active_corpus": CORPUS_NAME,
                "retrieval_top_k": RETRIEVAL_TOP_K,
                "downstream_effective_k": DOWNSTREAM_K,
                "retrieved_topk_chunk_ids": topk_ids,
                "retrieval_scores": scores,
                "fit_status": fit_status,
                "fit_expected_type": fit_expected,
                "fit_details": fit_details,
                "final_outcome": outcome,
                "step_count": 1,
                "stop_reason": stop,
                "answer": None,
                "failure_mode_auto": None,
            }
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    manifest = {
        "run_id": run_id,
        "run_date": run_date,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "simulated": False,
        "what_is_real_vs_constructed": {
            "corpus_pages": "REAL",
            "chunk_content": "REAL — direct PDF extraction (inherited from baseline_v0)",
            "chunk_ids_and_boundaries": "DETERMINISTIC — section-header rules (inherited)",
            "questions": "INHERITED from puzzlebook35 audit_v0.questions.jsonl",
            "runtime_metrics_jsonl": "REAL — BM25 baseline run output",
            "audit_labels": "n/a — this task does not produce audit rows",
        },
        "pdf_source": {
            "path": str(pdf_path.relative_to(REPO)) if pdf_path.exists() else "n/a (chunks reused)",
            "sha256": file_sha256(pdf_path) if pdf_path.exists() else "n/a",
            "page_range": [12, 38],
        },
        "questions_source": {
            "path": str(QUESTIONS_PATH.relative_to(REPO)),
            "sha256": file_sha256(QUESTIONS_PATH),
            "count": len(questions),
        },
        "corpus": {
            "name": CORPUS_NAME,
            "source_tag": SOURCE_TAG,
            "chunks_path": str(CORPUS_PATH.relative_to(REPO)),
            "chunks_sha256": file_sha256(CORPUS_PATH),
            "chunk_count": len(chunks),
            "shared_with": ["baseline_v0"],
        },
        "retrieval": {
            "method": "bm25_okapi",
            "library": "rank-bm25==0.2.2",
            "top_k": RETRIEVAL_TOP_K,
            "downstream_effective_k": DOWNSTREAM_K,
            "tokenizer": "lowercase + \\b\\w\\w+\\b (identical to baseline_v0 TF-IDF)",
            "k1": "default (1.5)",
            "b": "default (0.75)",
            "random_state": "n/a (no random component)",
        },
        "fit_check": {
            "version": "v0_minimal (inherited from baseline_v0)",
            "intent_rules": {
                "when": "regex (19|20)\\d{2} over downstream-effective-k chunks",
                "who": "regex capitalized name pattern",
                "how_many": "regex \\b\\d+\\b",
                "other": "skipped",
            },
        },
        "run": {
            "path": str(runs_path.relative_to(REPO)),
            "sha256": file_sha256(runs_path),
            "row_count": len(questions),
            "outcomes": outcomes,
            "fit_status_distribution": fit_dist,
        },
        "experiment": {
            "compared_against": "baseline_v0 (TF-IDF cosine)",
            "controlled_change": "retrieval scoring formula only",
            "everything_else_held_constant": [
                "chunks (same JSONL file, same SHA-256)",
                "questions (same JSONL file, same SHA-256)",
                "tokenizer (lowercase + \\b\\w\\w+\\b)",
                "fit_check policy and regex rules",
                "top_k=10, downstream_effective_k=4",
            ],
        },
    }
    manifest_path = MANIFESTS_DIR / f"{run_id}.manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")

    return {
        "chunks": len(chunks),
        "questions": len(questions),
        "outcomes": outcomes,
        "fit_dist": fit_dist,
        "runs_path": runs_path,
        "manifest_path": manifest_path,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=str(DEFAULT_PDF))
    ap.add_argument("--run-date", default=dt.date.today().isoformat())
    args = ap.parse_args()

    summary = run_pipeline(Path(args.pdf).resolve(), args.run_date)
    o = summary["outcomes"]
    fd = summary["fit_dist"]
    print(f"Chunks loaded: {summary['chunks']}")
    print(f"Run completed: {summary['questions']} / 35 questions processed (BM25)")
    print(
        f"Outcomes: hit={o.get('hit', 0)}, "
        f"fit_refuse={o.get('fit_refuse', 0)}, "
        f"given_up={o.get('given_up', 0)}"
    )
    print(
        f"fit_status distribution: match={fd.get('match', 0)}, "
        f"mismatch={fd.get('mismatch', 0)}, "
        f"partial={fd.get('partial', 0)}, "
        f"skipped={fd.get('skipped', 0)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
