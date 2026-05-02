"""Validator for baseline_v0 outputs.

Checks (per CC_TASK_BRIEF success criteria):
  * chunks JSONL: each line is JSON Schema valid, chunk_id is unique and
    matches pb_raw_\\d+, no whitespace in chunk_id, char_count matches content.
  * run JSONL: exactly 35 rows, qid set matches questions JSONL,
    retrieved_topk_chunk_ids ⊆ chunks chunk_ids, fit_status in known set,
    final_outcome in known set.
  * manifest: simulated == False; what_is_real_vs_constructed has expected keys;
    sha256 of chunks/runs files matches recorded values.

Exits 0 on success, 1 on failure with a list of errors.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

CHUNKS_PATH = REPO / "audits/puzzlebook35/corpus/puzzlebook_raw_chunks_v1.jsonl"
RUNS_DIR = REPO / "audits/puzzlebook35/runs"
MANIFESTS_DIR = REPO / "audits/puzzlebook35/manifests"
QUESTIONS_PATH = REPO / "audits/puzzlebook35/audit_v0.questions.jsonl"

CHUNK_SCHEMA = {
    "type": "object",
    "required": [
        "chunk_id", "source", "page", "section_path", "type",
        "content", "char_count", "extraction_method", "extraction_warnings",
    ],
    "properties": {
        "chunk_id": {"type": "string", "pattern": r"^pb_raw_\d+$"},
        "source": {"type": "string", "minLength": 1},
        "page": {"type": "integer"},
        "section_path": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "type": {"enum": ["prose", "code", "mixed"]},
        "content": {"type": "string", "minLength": 1},
        "char_count": {"type": "integer", "minimum": 1},
        "extraction_method": {"type": "string", "minLength": 1},
        "extraction_warnings": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}

RUN_SCHEMA = {
    "type": "object",
    "required": [
        "run_id", "qid", "question", "intent", "active_corpus",
        "retrieval_top_k", "downstream_effective_k",
        "retrieved_topk_chunk_ids", "retrieval_scores",
        "fit_status", "fit_expected_type", "fit_details",
        "final_outcome", "step_count", "stop_reason", "answer", "failure_mode_auto",
    ],
    "properties": {
        "run_id": {"type": "string"},
        "qid": {"type": "string", "pattern": r"^Q\d+$"},
        "question": {"type": "string"},
        "intent": {"type": "string"},
        "active_corpus": {"type": "string"},
        "retrieval_top_k": {"type": "integer", "minimum": 1},
        "downstream_effective_k": {"type": "integer", "minimum": 1},
        "retrieved_topk_chunk_ids": {"type": "array", "items": {"type": "string"}},
        "retrieval_scores": {"type": "object"},
        "fit_status": {"enum": ["match", "mismatch", "partial", "skipped"]},
        "fit_expected_type": {"type": "string"},
        "fit_details": {"type": "object"},
        "final_outcome": {"enum": ["hit", "fit_refuse", "given_up"]},
        "step_count": {"type": "integer", "minimum": 1},
        "stop_reason": {"type": "string"},
        "answer": {"type": ["string", "null"]},
        "failure_mode_auto": {"type": ["string", "null"]},
    },
    "additionalProperties": False,
}


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    out = []
    with path.open("r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            out.append(json.loads(ln))
    return out


def find_latest_run() -> tuple[Path, Path]:
    """Return (runs_jsonl_path, manifest_json_path) for latest baseline run."""
    candidates = sorted(RUNS_DIR.glob("*_v0_baseline.jsonl"))
    if not candidates:
        raise FileNotFoundError(f"No *_v0_baseline.jsonl under {RUNS_DIR}")
    runs_path = candidates[-1]
    manifest_path = MANIFESTS_DIR / f"{runs_path.stem}.manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest missing: {manifest_path}")
    return runs_path, manifest_path


def main() -> int:
    errors: list[str] = []

    if not CHUNKS_PATH.exists():
        print(f"ERROR: chunks file missing: {CHUNKS_PATH}")
        return 1

    chunks = load_jsonl(CHUNKS_PATH)
    chunk_ids: set[str] = set()
    for i, ch in enumerate(chunks):
        try:
            jsonschema.validate(ch, CHUNK_SCHEMA)
        except jsonschema.ValidationError as e:
            errors.append(f"chunks[{i}] ({ch.get('chunk_id', '?')}): schema fail: {e.message}")
            continue
        cid = ch["chunk_id"]
        if any(c.isspace() for c in cid):
            errors.append(f"chunks[{i}]: chunk_id contains whitespace: {cid!r}")
        if cid in chunk_ids:
            errors.append(f"chunks[{i}]: duplicate chunk_id: {cid}")
        chunk_ids.add(cid)
        if len(ch["content"]) != ch["char_count"]:
            errors.append(
                f"chunks[{i}] ({cid}): char_count={ch['char_count']} != "
                f"len(content)={len(ch['content'])}"
            )

    runs_path, manifest_path = find_latest_run()
    runs = load_jsonl(runs_path)

    if len(runs) != 35:
        errors.append(f"runs JSONL has {len(runs)} rows, expected 35")

    questions = load_jsonl(QUESTIONS_PATH)
    expected_qids = {q["qid"] for q in questions}
    actual_qids = {r["qid"] for r in runs}
    if expected_qids != actual_qids:
        missing = expected_qids - actual_qids
        extra = actual_qids - expected_qids
        if missing:
            errors.append(f"runs missing qids: {sorted(missing)}")
        if extra:
            errors.append(f"runs has unexpected qids: {sorted(extra)}")

    for i, row in enumerate(runs):
        try:
            jsonschema.validate(row, RUN_SCHEMA)
        except jsonschema.ValidationError as e:
            errors.append(f"runs[{i}] ({row.get('qid', '?')}): schema fail: {e.message}")
            continue
        for cid in row["retrieved_topk_chunk_ids"]:
            if cid not in chunk_ids:
                errors.append(
                    f"runs[{i}] ({row['qid']}): retrieved chunk_id not in corpus: {cid}"
                )

    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    if manifest.get("simulated") is not False:
        errors.append(f"manifest.simulated must be False, got {manifest.get('simulated')!r}")

    expected_keys = {
        "corpus_pages", "chunk_content", "chunk_ids_and_boundaries",
        "questions", "runtime_metrics_jsonl", "audit_labels",
    }
    real = manifest.get("what_is_real_vs_constructed", {})
    missing = expected_keys - real.keys()
    if missing:
        errors.append(f"manifest.what_is_real_vs_constructed missing keys: {sorted(missing)}")

    actual_chunks_sha = file_sha256(CHUNKS_PATH)
    if manifest.get("corpus", {}).get("chunks_sha256") != actual_chunks_sha:
        errors.append(
            f"manifest corpus.chunks_sha256 mismatch: "
            f"{manifest.get('corpus', {}).get('chunks_sha256')} != {actual_chunks_sha}"
        )
    actual_runs_sha = file_sha256(runs_path)
    if manifest.get("run", {}).get("sha256") != actual_runs_sha:
        errors.append(
            f"manifest run.sha256 mismatch: "
            f"{manifest.get('run', {}).get('sha256')} != {actual_runs_sha}"
        )

    if errors:
        print(f"VALIDATION FAILED ({len(errors)} errors):")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"OK: chunks={len(chunks)} runs={len(runs)} manifest={manifest_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
