# audit_v0.manual.jsonl — schema extension notes

This file documents non-Pack-defined fields added to audit rows in
`audit_v0.manual.jsonl` during the baseline_v0 / fitcheck_v1 work
(commits between `595f010` and `f002b26`). Pack-defined fields are
unchanged; the additions are backward-compatible and live alongside
the original schema.

## New field: `raw_corpus_confirmation`

**Purpose.** Make empirical raw-data findings about each audit row
queryable from the audit JSONL itself, without requiring the reader
to spelunk through `baseline_v0/NOTES.md`, `FITCHECK_AUDIT.md`, and
`fitcheck_v1/COMPARE_v0_v1_fitcheck.md` to learn whether and how an
audit row's predictions held under real retrieval + fit_check.

**When present.** On rows that have been re-checked against the raw
PDF-extracted chunks corpus produced by `baseline_v0` and re-scored
through both retrievals (TF-IDF, BM25) × both fit_check policies
(v0 regex, v1 hybrid). Currently: Q2, Q7, Q22.

**Backward compatibility.** Rows without this field are pre-confirmation;
rows with it have been verified on the raw 30-chunk corpus
(`audits/puzzlebook35/corpus/puzzlebook_raw_chunks_v1.jsonl`).

**Source script.** `update_audit_v0_with_raw_confirmation.py`
(idempotent — re-running with no changes leaves the file byte-identical).

## Field structure

```jsonc
"raw_corpus_confirmation": {
  "confirmed_at": "<YYYY-MM-DD>",
  "raw_corpus_path": "audits/puzzlebook35/corpus/puzzlebook_raw_chunks_v1.jsonl",
  "raw_corpus_sha256": "<hex>",
  "raw_corpus_chunk_count": 30,

  // Mapping from paraphrased namespace to raw namespace, by typed
  // evidence (NOT by chunk_id renaming).
  "gold_chunk_id_raw":  "<chunk_id or null>",
  "gold_chunk_uniqueness": "<short prose: why this chunk uniquely satisfies expected_evidence, or n/a>",
  "decoy_chunk_ids_raw": [
    {
      "chunk_id": "<chunk_id>",
      "matched_forbidden_pattern": "<verbatim string from forbidden_evidence>",
      "paraphrased_decoy_analog": "<paraphrased chunk_id, if any>"
    }
  ],

  // 2×2 grid of (retrieval_method × fit_check_version) outcomes.
  // Cell labels: "v0_tfidf_x_fitcheck_v0_regex", "v0_tfidf_x_fitcheck_v1_hybrid",
  //              "v1_bm25_x_fitcheck_v0_regex",  "v1_bm25_x_fitcheck_v1_hybrid"
  "outcomes_grid": {
    "<cell_label>": {"fit_status": "...", "final_outcome": "...", "top1_chunk_id": "..."}
  },

  // Which audit row predictions held under empirical re-check.
  // Keys are row-specific; common ones:
  //   gold_in_top_1                          (bool)
  //   expected_evidence_satisfied            (bool — mirrors original audit field)
  //   fit_status_matches_audit               (bool | "under_<grid_cell>_only")
  //   final_outcome_matches_audit            (bool | "under_<grid_cell>_only")
  //   negative_lesson_holds                  (bool)
  //   machine_verifiable_check_holds         (bool — for rows with such checks)
  //   answerable_in_corpus_<bool>_holds      (bool)
  //   decoy_class_materialized_as_predicted  (bool)
  //   evidence_verdict_underdetermined_holds (bool)
  "predictions_held": { "<key>": <bool|string>, ... },

  // Operational failure modes empirically observed during baseline runs.
  // Distinct from row-level `failure_mode_audit` (semantic property of
  // question/data) — these describe what the system actually did wrong.
  "failure_modes_observed_empirically": [ "<failure_mode_name>", ... ],
  "failure_modes_descriptions": { "<failure_mode_name>": "<short prose>", ... },

  "evidence_paths": [ "<repo-relative path[#section_anchor]>", ... ],

  // Recommendation for retrospective audit_confidence upgrade. NOT
  // applied unilaterally to the row's top-level `audit_confidence`.
  // Future re-labeling can choose to honor or override.
  "audit_confidence_after_raw_recommendation": "<low|medium|high>",

  "notes": "<short prose>"
}
```

## Failure-mode names used

These names are project-local. They are **not** in the canonical Pack
failure_mode taxonomy (per CC_TASK_BRIEF, Pack patches are out of scope
for this work). Listed here for reference; future taxonomy formalization
is a separate task.

| name | first observed | short description | evidence path |
|---|---|---|---|
| `lexical_pattern_overmatch` | Q7 (NOTES §5) | regex/lexical fit_check matches material that does not satisfy intent semantics; in v0, applies to who-regex (100% chunk-coverage) and how_many-regex (73%) | `baseline_v0/NOTES.md#5`, `FITCHECK_AUDIT.md` |
| `generic_chunk_dominance` | NOTES §4 false-hits | short generic prose chunk with broad vocabulary wins retrieval over specific subsection containing the answer; persists across TF-IDF and BM25 | `baseline_v1_bm25/COMPARE_v0_v1.md` |
| `out_of_scope_within_topic` | Q26/Q31 | retrieval finds the right topic chunk but the question's answer category lives outside `active_corpus`; fit_refuse possible via section-path/digit gate (fitcheck_v1) | `fitcheck_v1/COMPARE_v0_v1_fitcheck.md`, `baseline_v0/NOTES.md#2` |
| `not_in_corpus` | Q22 (Pack-canonical) | the answer-bearing material does not exist in active_corpus; system should fit_refuse | `baseline_v0/NOTES.md#3` |

`not_in_corpus` is the only Pack-canonical entry in this list; the
other three are emergent from the empirical work.

## How to query

```bash
# rows with raw confirmation:
jq -c 'select(.raw_corpus_confirmation != null) | {qid, holds: .raw_corpus_confirmation.predictions_held}' \
   audits/puzzlebook35/audit_v0.manual.jsonl

# rows that observed lexical_pattern_overmatch:
jq -c 'select(.raw_corpus_confirmation.failure_modes_observed_empirically | index("lexical_pattern_overmatch"))' \
   audits/puzzlebook35/audit_v0.manual.jsonl

# 2×2 grid for a specific qid:
jq '.raw_corpus_confirmation.outcomes_grid' \
   <(grep '"qid": "Q7"' audits/puzzlebook35/audit_v0.manual.jsonl)
```
