"""One-time merge: add `raw_corpus_confirmation` field to each audit row in
`audits/puzzlebook35/audit_v0.manual.jsonl`, transferring empirical findings
from baseline_v0/NOTES.md, FITCHECK_AUDIT.md, and fitcheck_v1/COMPARE.

Idempotent: if `raw_corpus_confirmation` already present and equal, no change.
Backward-compatible: existing fields are preserved in their original order.
Determinism: Python 3.7+ dict preserves insertion order; output is one JSON
line per row, no indent, ensure_ascii=False.

After running, audit_v0.manual.jsonl can be queried for raw-data
confirmation status without spelunking through NOTES sections.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIT_PATH = HERE / "audit_v0.manual.jsonl"
CORPUS_PATH = HERE / "corpus" / "puzzlebook_raw_chunks_v1.jsonl"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for blk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(blk)
    return h.hexdigest()


def chunk_count(path: Path) -> int:
    n = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                n += 1
    return n


CONFIRMED_AT = "2026-05-02"
RETRIEVAL_LABELS = ("v0_tfidf", "v1_bm25")
FITCHECK_LABELS = ("v0_regex", "v1_hybrid")

EVIDENCE_PATHS_COMMON = [
    "audits/puzzlebook35/baseline_v0/NOTES.md",
    "audits/puzzlebook35/baseline_v0/FITCHECK_AUDIT.md",
    "audits/puzzlebook35/baseline_v0/FITCHECK_V1_DESIGN.md",
    "audits/puzzlebook35/fitcheck_v1/COMPARE_v0_v1_fitcheck.md",
]


def grid_cell(fit_status: str, final_outcome: str, top1: str | None) -> dict:
    out = {"fit_status": fit_status, "final_outcome": final_outcome}
    if top1 is not None:
        out["top1_chunk_id"] = top1
    return out


def confirmation_for_q2(corpus_sha: str, n_chunks: int) -> dict:
    return {
        "confirmed_at": CONFIRMED_AT,
        "raw_corpus_path": "audits/puzzlebook35/corpus/puzzlebook_raw_chunks_v1.jsonl",
        "raw_corpus_sha256": corpus_sha,
        "raw_corpus_chunk_count": n_chunks,
        "gold_chunk_id_raw": "pb_raw_09",
        "gold_chunk_uniqueness": "unique container of pygame AND PythonTurtle in pp.12-38",
        "decoy_chunk_ids_raw": [
            {
                "chunk_id": "pb_raw_07",
                "matched_forbidden_pattern": "mentions of pip in install context without naming both specific modules",
                "paraphrased_decoy_analog": "pb_intro_004",
            }
        ],
        "outcomes_grid": {
            "v0_tfidf_x_fitcheck_v0_regex":   grid_cell("skipped", "hit",  "pb_raw_09"),
            "v0_tfidf_x_fitcheck_v1_hybrid":  grid_cell("match",   "hit",  "pb_raw_09"),
            "v1_bm25_x_fitcheck_v0_regex":    grid_cell("skipped", "hit",  "pb_raw_09"),
            "v1_bm25_x_fitcheck_v1_hybrid":   grid_cell("match",   "hit",  "pb_raw_09"),
        },
        "predictions_held": {
            "gold_in_top_1": True,
            "expected_evidence_satisfied": True,
            "fit_status_matches_audit": True,
            "final_outcome_matches_audit": True,
            "decoy_class_materialized_as_predicted": True,
        },
        "failure_modes_observed_empirically": [],
        "evidence_paths": EVIDENCE_PATHS_COMMON + ["audits/puzzlebook35/baseline_v0/NOTES.md#6"],
        "audit_confidence_after_raw_recommendation": "high",
        "notes": (
            "Q-known-hit confirmed across all 4 retrieval × fit_check combinations. "
            "Original audit_confidence=medium because chunks were paraphrased and "
            "rater also constructed questions; the paraphrased-chunks caveat is "
            "now removed by raw confirmation. Recommendation 'high' is for any "
            "future re-labeling — not unilaterally applied to top-level "
            "audit_confidence in this row."
        ),
    }


def confirmation_for_q7(corpus_sha: str, n_chunks: int) -> dict:
    return {
        "confirmed_at": CONFIRMED_AT,
        "raw_corpus_path": "audits/puzzlebook35/corpus/puzzlebook_raw_chunks_v1.jsonl",
        "raw_corpus_sha256": corpus_sha,
        "raw_corpus_chunk_count": n_chunks,
        "gold_chunk_id_raw": None,
        "gold_chunk_uniqueness": "n/a — answerable_in_corpus=false; no authorship statement in pp.12-38",
        "decoy_chunk_ids_raw": None,
        "outcomes_grid": {
            "v0_tfidf_x_fitcheck_v0_regex":   grid_cell("match",    "hit",         "pb_raw_05"),
            "v0_tfidf_x_fitcheck_v1_hybrid":  grid_cell("mismatch", "fit_refuse",  "pb_raw_05"),
            "v1_bm25_x_fitcheck_v0_regex":    grid_cell("match",    "hit",         "pb_raw_05"),
            "v1_bm25_x_fitcheck_v1_hybrid":   grid_cell("mismatch", "fit_refuse",  "pb_raw_05"),
        },
        "predictions_held": {
            "expected_evidence_satisfied": False,
            "evidence_verdict_underdetermined_holds": True,
            "fit_status_matches_audit": "under_v1_hybrid_only",
            "final_outcome_matches_audit": "under_v1_hybrid_only (audit said given_up; v1 fit_refuse is the operational realization of the audit row's negative_lesson)",
            "negative_lesson_holds": True,
        },
        "failure_modes_observed_empirically": [
            "lexical_pattern_overmatch",
            "generic_chunk_dominance",
        ],
        "failure_modes_descriptions": {
            "lexical_pattern_overmatch": (
                "v0 who-regex matched 10 capitalized non-name tokens "
                "(Python, Всюду, Выглядит, Для, Добро, Если, Задачи, "
                "Знакомство, Или, Их) in top-4 of pb_raw_05; "
                "fit_status=match was structurally guaranteed by the corpus "
                "(NAME_RE matches 30/30 chunks per FITCHECK_AUDIT). "
                "v1 hybrid requires +авTOR/+написал trigger conjunction → mismatch."
            ),
            "generic_chunk_dominance": (
                "Top-1 across both retrievals (TF-IDF and BM25) was pb_raw_05 "
                "(Введение, broad vocabulary), not because it contains "
                "authorship material but because it shares lexical surface with "
                "many low-specificity questions. Documented in baseline_v1_bm25/"
                "COMPARE_v0_v1.md."
            ),
        },
        "evidence_paths": EVIDENCE_PATHS_COMMON + [
            "audits/puzzlebook35/baseline_v0/NOTES.md#5",
            "audits/puzzlebook35/baseline_v1_bm25/COMPARE_v0_v1.md",
        ],
        "audit_confidence_after_raw_recommendation": "high",
        "notes": (
            "Audit row's ambiguity diagnosis confirmed via two independent "
            "operational failure modes. v1 fit_check correctly refuses for the "
            "audit row's stated reason (no authorship-relation marker), closing "
            "the audit-row-as-prediction → empirical-confirmation loop. "
            "First row of three on this corpus to demonstrate that an audit "
            "row's negative_lesson can be operationalized as an executable "
            "fit_check rule (v1 trigger requirement)."
        ),
    }


def confirmation_for_q22(corpus_sha: str, n_chunks: int) -> dict:
    return {
        "confirmed_at": CONFIRMED_AT,
        "raw_corpus_path": "audits/puzzlebook35/corpus/puzzlebook_raw_chunks_v1.jsonl",
        "raw_corpus_sha256": corpus_sha,
        "raw_corpus_chunk_count": n_chunks,
        "gold_chunk_id_raw": None,
        "gold_chunk_uniqueness": "n/a — not_in_corpus_test; corpus has zero year tokens",
        "decoy_chunk_ids_raw": None,
        "outcomes_grid": {
            "v0_tfidf_x_fitcheck_v0_regex":   grid_cell("mismatch", "fit_refuse", "pb_raw_26"),
            "v0_tfidf_x_fitcheck_v1_hybrid":  grid_cell("mismatch", "fit_refuse", "pb_raw_26"),
            "v1_bm25_x_fitcheck_v0_regex":    grid_cell("mismatch", "fit_refuse", "pb_raw_26"),
            "v1_bm25_x_fitcheck_v1_hybrid":   grid_cell("mismatch", "fit_refuse", "pb_raw_26"),
        },
        "predictions_held": {
            "answerable_in_corpus_false_holds": True,
            "machine_verifiable_check_holds": True,
            "expected_evidence_satisfied": False,
            "fit_status_matches_audit": True,
            "final_outcome_matches_audit": True,
            "decoy_class_materialized_as_predicted": True,
        },
        "failure_modes_observed_empirically": ["not_in_corpus"],
        "failure_modes_descriptions": {
            "not_in_corpus": (
                "Audit row machine-verifiable check `\\b(19|20)\\d{2}\\b → 0 hits` "
                "across 27 paraphrased chunks holds on 30 raw chunks. "
                "The forbidden_evidence numeric decoy class anticipated in audit row "
                "(version numbers, URL paths, problem data) materialized as ASCII "
                "codes 80/114/111 in pb_raw_26 (Задача 12) — top-1 in both "
                "retrievals — and was correctly excluded by year-regex in v0 and "
                "by year+temporal-trigger conjunction in v1."
            ),
        },
        "evidence_paths": EVIDENCE_PATHS_COMMON + [
            "audits/puzzlebook35/baseline_v0/NOTES.md#3",
        ],
        "audit_confidence_after_raw_recommendation": "high",
        "notes": (
            "First audit row on this project to receive cross-method empirical "
            "confirmation: machine-verifiable check holds across paraphrased→raw "
            "corpus change, across TF-IDF→BM25 retrieval change, and across "
            "v0→v1 fit_check change. Strong sanity-floor for the framework."
        ),
    }


CONFIRMATIONS_BY_QID = {
    "Q2":  confirmation_for_q2,
    "Q7":  confirmation_for_q7,
    "Q22": confirmation_for_q22,
}


def main() -> int:
    if not AUDIT_PATH.exists():
        print(f"missing: {AUDIT_PATH}", file=sys.stderr)
        return 1
    if not CORPUS_PATH.exists():
        print(f"missing: {CORPUS_PATH}", file=sys.stderr)
        return 1

    corpus_sha = file_sha256(CORPUS_PATH)
    n_chunks = chunk_count(CORPUS_PATH)

    rows = []
    for line in AUDIT_PATH.open("r", encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))

    changed = 0
    for r in rows:
        qid = r["qid"]
        builder = CONFIRMATIONS_BY_QID.get(qid)
        if builder is None:
            continue
        new_field = builder(corpus_sha, n_chunks)
        existing = r.get("raw_corpus_confirmation")
        if existing == new_field:
            continue
        r["raw_corpus_confirmation"] = new_field
        changed += 1

    with AUDIT_PATH.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Updated {changed} of {len(rows)} rows in {AUDIT_PATH.name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
