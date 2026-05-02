# FITCHECK_V2_DESIGN — per-intent alignment floor + ё-normalization

Status: **proposal**. No v2 code yet. Pre-registered before implementation
to prevent metric-retrofit (lesson from v1's misspecified match-rate
criterion).

## Goal

Close the 4 of 6 unflipped NOTES §4 false-hits that `fitcheck_v1` left
intact, **without regressing any of the 14 known-correct hits or the
3 pilot canaries (Q2/Q7/Q22)**.

| qid | intent | v1 outcome | v2 target | reason v1 missed it |
|-----|--------|------------|-----------|---------------------|
| Q9  | how    | match→hit  | mismatch→fit_refuse | low alignment with `pb_raw_05`, but ≥2 floor lets it through |
| Q13 | why    | match→hit  | mismatch→fit_refuse | alignment 3 with `pb_raw_09`; passes ≥2 floor; no why-trigger nearby |
| Q16 | why    | match→hit  | mismatch→fit_refuse | alignment 2 with `pb_raw_11`; passes ≥2 floor; no why-trigger nearby |
| Q29 | how    | match→hit  | mismatch→fit_refuse | alignment 2 with `pb_raw_05`; passes ≥2 floor; no how-trigger nearby |

The other two unflipped (Q11 multi-chunk reasoning, Q34 semantic
specificity) are **out of v2 scope** — they need cross-chunk aggregation
or rare-token noun-anchoring, both significantly larger design surface.

## Constraints (firm, inherited)

- No LLM, no embeddings, pure Python + PyPI.
- Deterministic, byte-stable JSONL outputs.
- Backward-compatible to v1: same module signature `fit_check(intent,
  question, topk_chunk_ids, chunks_by_id, downstream_k)` returning
  `(fit_status, fit_expected_type, fit_details)`.

## What v2 changes

Two narrow changes to the v1 hybrid policy:

### Change 1: per-intent alignment floor

v1 uses a global `ALIGN_FLOOR_MATCH = 2` for all alignment-driven
intents (`what`, `why`, `how`). v2 splits this:

```python
ALIGN_FLOOR_BY_INTENT = {
    "what": 2,   # unchanged — Q1 (alignment 2) needs this
    "why":  4,   # raised — kills Q13 (3) and Q16 (2); preserves Q23 (6), Q32 (5+)
    "how":  4,   # raised — kills Q9 (1-2) and Q29 (2); preserves Q21 (4+), Q27 (3+)
}
```

Manually traced (`audits/puzzlebook35/baseline_v0/audit_fitcheck.py`-style
analysis) for each affected qid — see `## Falsifiability` below for
the per-qid commitment table.

### Change 2: ё/е normalization in tokenize

v1 tokenizer treats `ё` and `е` as distinct characters. Russian
orthography commonly substitutes one for the other, breaking
prefix-5 stem matches: `серьёзной → серьё` ≠ `серьезные → серье`.

v2 normalizes `ё → е` before stemming:

```python
def normalize_yo(s: str) -> str:
    return s.replace("ё", "е").replace("Ё", "Е")
```

Applied in `tokenize()` before the lowercase pass.

This change is small, lossless for the corpus, and unlikely to introduce
regressions.

## What v2 does NOT change

- Trigger-window logic for {when, who, how_many} — unchanged.
- OOS gate — unchanged (digit-near-term heuristic stays).
- Top-level dispatcher — unchanged.
- Run JSONL schema — unchanged.

## What v2 does NOT fix (deferred)

- **Q11** (multi-chunk reasoning). Single-chunk fit_check fundamentally
  cannot adjudicate "in which of tasks 1-15 does X happen". v3 could
  introduce per-intent aggregation, out of scope here.
- **Q34** (semantic specificity). The question asks about Серьезные
  task difficulty progression; correct chunk (`pb_raw_14`) is the
  Серьезные intro paragraph. False-hit chunk (`pb_raw_11`, Нотация O)
  also discusses сложность. Without rare-token anchoring or
  section_path matching (Approach C), v2 lexical methods cannot
  distinguish them.

## Falsifiability — pre-registered before implementation

### Per-qid commitments

Each row is a binding prediction. v2 implementation must hit every cell;
deviations require revisiting the design, not patching the test.

| qid | intent | role | v1 actual | **v2 commitment** |
|-----|--------|------|-----------|-------------------|
| Q1  | what   | known-correct (low-alignment) | match→hit | match→hit (no regression on what≥2) |
| Q2  | what   | Q-known-hit canary | match→hit | match→hit (canary) |
| Q4  | what   | known-correct | match→hit | match→hit |
| Q7  | who    | ambiguity canary | mismatch→fit_refuse | mismatch→fit_refuse (canary) |
| Q8  | what   | known-correct | match→hit | match→hit |
| Q9  | how    | NOTES §4 false-hit | match→hit | **mismatch→fit_refuse** (flip) |
| Q11 | what   | NOTES §4 false-hit (multi-chunk) | match→hit | match→hit (out of scope) |
| Q13 | why    | NOTES §4 false-hit | match→hit | **mismatch→fit_refuse** (flip) |
| Q16 | why    | NOTES §4 false-hit | match→hit | **mismatch→fit_refuse** (flip) |
| Q21 | how    | known-correct (`pb_raw_05` is right answer) | match→hit | match→hit (no regression) |
| Q22 | when   | not_in_corpus canary | mismatch→fit_refuse | mismatch→fit_refuse (canary) |
| Q23 | why    | known-correct (`pb_raw_13` numbered list) | match→hit | match→hit (no regression on why≥4) |
| Q26 | how    | OOS (v1) | mismatch→fit_refuse | mismatch→fit_refuse (preserve OOS) |
| Q29 | how    | NOTES §4 false-hit | match→hit | **mismatch→fit_refuse** (flip) |
| Q31 | how    | OOS (v1) | mismatch→fit_refuse | mismatch→fit_refuse (preserve OOS) |
| Q32 | why    | known-correct (`pb_raw_05` mentions "решать по порядку") | match→hit | match→hit (no regression on why≥4) |
| Q34 | how    | NOTES §4 false-hit (semantic specificity) | match→hit | match→hit (out of scope) |

### Aggregate criteria

| metric | v1 actual | **v2 success criterion** |
|--------|-----------|--------------------------|
| `fit_refuse` count | 5/35 | **≥ 8/35** (v1's 5 + Q9/Q13/Q16/Q29) |
| Pilot canaries unchanged | yes (Q2 match, Q7 refuse, Q22 refuse) | **yes** |
| Regressions on 14 known-correct | 0 | **0** |
| Q9/Q13/Q16/Q29 flipped to fit_refuse | n/a | **all 4** |
| Determinism (re-run sha256) | yes | **yes** |

### Replacement for the misspecified v1 match-rate metric

v1 falsifiability included `match rate ≤ 50%` which proved misspecified
(corpus-question relevance was higher than assumed). v2 replaces this
with **discriminative power on labeled set**:

> Discriminative power = (# correctly-flipped false-hits + # correctly-held
> known-correct) / (# total labeled rows)

Labeled set: 10 NOTES §4 false-hits + 14 known-correct = 24 rows.

| metric | v1 actual | **v2 success criterion** |
|--------|-----------|--------------------------|
| Discriminative power | (4 + 14) / 24 = 75% | **≥ 87.5%** (8/10 + 14/14 = 22/24) |

If v2 hits ≥ 87.5%, the design works; if it falls short while still
meeting per-qid commitments, design needs review.

### Pre-registration rule (inherited from v1)

If v2 fails ≥ 2 of the criteria above, the design is wrong, not the
implementation — revisit before iterating.

## Where v2 lives

`audits/puzzlebook35/fitcheck_v2/` parallel to `fitcheck_v1/`. Same
module shape (lexicons.py, fitcheck_v2.py, pipeline.py,
test_fitcheck_v2.py, validate_outputs.py, README.md, COMPARE doc).
v2 imports from v1 where possible to minimize duplication.

## Re-run scope

Same as v1: re-score both retrievals (TF-IDF, BM25) → 2×3 grid total
(retrieval × {fc_v0, fc_v1, fc_v2}). New outputs:

```
runs/<DATE>_v0_fitchk2.jsonl
runs/<DATE>_v1_fitchk2.jsonl
manifests/<DATE>_v0_fitchk2.manifest.json
manifests/<DATE>_v1_fitchk2.manifest.json
```

The 2×2 v1 outcomes_grid in `audit_v0.manual.jsonl` is extended to 2×3
by adding `v0_tfidf_x_fitcheck_v2_hybrid` and
`v1_bm25_x_fitcheck_v2_hybrid` cells. Backward-compatible per
AUDIT_SCHEMA_NOTES.md conventions.

## Implementation outline

1. `fitcheck_v2/lexicons.py` — re-export v1 lexicons + add `normalize_yo`.
2. `fitcheck_v2/fitcheck_v2.py` — import v1, override:
   - `tokenize()` — apply `normalize_yo` before lowercase
   - `fit_check_alignment()` — read floor from `ALIGN_FLOOR_BY_INTENT`
3. `fitcheck_v2/pipeline.py` — same shape as v1 pipeline, output `_fitchk2.jsonl`
4. `fitcheck_v2/test_fitcheck_v2.py` — focused tests on the 4 flips +
   no-regression on Q1/Q23/Q32
5. `fitcheck_v2/validate_outputs.py` — same delegation pattern as v1
6. `fitcheck_v2/COMPARE_v1_v2_fitcheck.md` — diff vs v1, falsifiability
   scoreboard from this doc
7. Re-run `update_audit_v0_with_raw_confirmation.py` extended to add
   v2 cells to outcomes_grid (or a new script `update_..._with_v2.py`)
