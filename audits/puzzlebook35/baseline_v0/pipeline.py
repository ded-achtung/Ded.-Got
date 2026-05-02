"""Baseline retrieval pipeline: PDF -> raw chunks -> TF-IDF top-k for 35 questions.

Usage:
    python -m audits.puzzlebook35.baseline_v0.pipeline
or:
    python pipeline.py        (from the baseline_v0 directory)

Outputs (relative to repo root):
    audits/puzzlebook35/corpus/puzzlebook_raw_chunks_v1.jsonl
    audits/puzzlebook35/runs/<RUN_DATE>_v0_baseline.jsonl
    audits/puzzlebook35/manifests/<RUN_DATE>_v0_baseline.manifest.json
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

from extractor import (  # noqa: E402
    PAGE_FROM,
    PAGE_TO,
    chunk_pages,
    extract_pages,
    write_chunks_jsonl,
)
from retriever import (  # noqa: E402
    DOWNSTREAM_K,
    RETRIEVAL_TOP_K,
    Chunk as RChunk,
    build_index,
    fit_check,
    final_outcome,
    load_chunks,
    retrieve,
    stop_reason,
)

DEFAULT_PDF = REPO / "Python в задачах и упражнениях.pdf"
QUESTIONS_PATH = REPO / "audits" / "puzzlebook35" / "audit_v0.questions.jsonl"
CORPUS_DIR = REPO / "audits" / "puzzlebook35" / "corpus"
RUNS_DIR = REPO / "audits" / "puzzlebook35" / "runs"
MANIFESTS_DIR = REPO / "audits" / "puzzlebook35" / "manifests"

CORPUS_NAME = "puzzlebook_raw_intro_t1_15"
SOURCE_TAG = "whiteside_puzzlebook_2025_ru"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def file_sha256_text(path: Path) -> str:
    """SHA256 of file contents for text files (LF normalized)."""
    return file_sha256(path)


def load_questions(path: Path) -> list[dict]:
    out: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def run_pipeline(pdf_path: Path, run_date: str) -> dict:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if not QUESTIONS_PATH.exists():
        raise FileNotFoundError(f"Questions JSONL not found: {QUESTIONS_PATH}")

    pages = extract_pages(pdf_path, PAGE_FROM, PAGE_TO)

    empty_pages = [p for p, lines in pages if not lines]
    if empty_pages:
        raise RuntimeError(
            f"pdftotext returned no content for pages: {empty_pages}. "
            "Refusing to silently fall back."
        )

    chunks = chunk_pages(pages)
    chunk_ids = [c.chunk_id for c in chunks]
    if len(set(chunk_ids)) != len(chunk_ids):
        raise RuntimeError("chunk_id collision detected — extractor bug")
    if len(chunks) < 25:
        raise RuntimeError(
            f"Too few chunks extracted ({len(chunks)} < 25). "
            "Either page range or chunker rules are broken."
        )

    chunks_path = CORPUS_DIR / "puzzlebook_raw_chunks_v1.jsonl"
    write_chunks_jsonl(chunks, chunks_path)

    rchunks = load_chunks(chunks_path)
    chunks_by_id = {c.chunk_id: c for c in rchunks}
    vec, X = build_index(rchunks)

    questions = load_questions(QUESTIONS_PATH)
    if len(questions) != 35:
        raise RuntimeError(f"Expected 35 questions, got {len(questions)}")

    run_id = f"{run_date}_v0_baseline"
    runs_path = RUNS_DIR / f"{run_id}.jsonl"
    runs_path.parent.mkdir(parents=True, exist_ok=True)

    outcomes = {"hit": 0, "fit_refuse": 0, "given_up": 0}
    fit_dist = {"match": 0, "mismatch": 0, "partial": 0, "skipped": 0}

    with runs_path.open("w", encoding="utf-8") as f:
        for q in questions:
            qid = q["qid"]
            question = q["question"]
            intent = q.get("intent", "what")
            topk_pairs = retrieve(question, vec, X, rchunks, top_k=RETRIEVAL_TOP_K)
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
            "chunk_content": "REAL — direct PDF extraction",
            "chunk_ids_and_boundaries": "DETERMINISTIC — section-header rules",
            "questions": "INHERITED from puzzlebook35 audit_v0.questions.jsonl",
            "runtime_metrics_jsonl": "REAL — TF-IDF baseline run output",
            "audit_labels": "n/a — this task does not produce audit rows",
        },
        "pdf_source": {
            "path": str(pdf_path.relative_to(REPO)),
            "sha256": file_sha256(pdf_path),
            "page_range": [PAGE_FROM, PAGE_TO],
        },
        "questions_source": {
            "path": str(QUESTIONS_PATH.relative_to(REPO)),
            "sha256": file_sha256_text(QUESTIONS_PATH),
            "count": len(questions),
        },
        "corpus": {
            "name": CORPUS_NAME,
            "source_tag": SOURCE_TAG,
            "chunks_path": str(chunks_path.relative_to(REPO)),
            "chunks_sha256": file_sha256_text(chunks_path),
            "chunk_count": len(chunks),
        },
        "retrieval": {
            "method": "tfidf_cosine",
            "library": "scikit-learn",
            "top_k": RETRIEVAL_TOP_K,
            "downstream_effective_k": DOWNSTREAM_K,
            "tokenizer": "TfidfVectorizer default + token_pattern \\b\\w\\w+\\b, lowercase=True",
            "random_state": "n/a (no random component)",
        },
        "fit_check": {
            "version": "v0_minimal",
            "intent_rules": {
                "when": "regex (19|20)\\d{2} over downstream-effective-k chunks",
                "who": "regex capitalized name pattern",
                "how_many": "regex \\b\\d+\\b",
                "other": "skipped",
            },
        },
        "run": {
            "path": str(runs_path.relative_to(REPO)),
            "sha256": file_sha256_text(runs_path),
            "row_count": len(questions),
            "outcomes": outcomes,
            "fit_status_distribution": fit_dist,
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
        "chunks_path": chunks_path,
        "runs_path": runs_path,
        "manifest_path": manifest_path,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=str(DEFAULT_PDF), help="Path to puzzlebook PDF")
    ap.add_argument(
        "--run-date",
        default=dt.date.today().isoformat(),
        help="YYYY-MM-DD label for run_id (default: today)",
    )
    args = ap.parse_args()

    pdf = Path(args.pdf).resolve()
    summary = run_pipeline(pdf, args.run_date)

    o = summary["outcomes"]
    fd = summary["fit_dist"]
    print(f"Chunks extracted: {summary['chunks']} (from pp.{PAGE_FROM}-{PAGE_TO})")
    print(f"Run completed: {summary['questions']} / 35 questions processed")
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
