# fitcheck_v1 — non-regex hybrid fit_check policy

Implementation of the design committed in
`audits/puzzlebook35/baseline_v0/FITCHECK_V1_DESIGN.md` (commit `595f010`).

Replaces v0's three bare-regex rules (`who`/`when`/`how_many` always-match
problem documented in `baseline_v0/FITCHECK_AUDIT.md`) with:

- **Trigger-window conjunctions** (Approach A) for {when, who, how_many}:
  candidate token + intent_trigger within ±12 + question_keyword within ±25.
- **Lexical alignment floor** for {what, why, how}: ≥2 question content
  tokens overlap with chunk content tokens (after stop-list + prefix-5
  stem) → match; ≥1 → partial; 0 → mismatch.
- **Section-path / out-of-scope gate** for `решение`/`решить`/`ответ`
  questions with task-number reference: fit_refuse if no Решения section
  appears in top-k.

## Module layout

```
audits/puzzlebook35/fitcheck_v1/
  lexicons.py             — RU stop-list, interrogatives, intent triggers,
                            cardinals, OOS terms, prefix-5 stem
  fitcheck_v1.py          — fit_check() dispatcher + per-intent logic
  pipeline.py             — re-scores existing run JSONLs through v1
  test_fitcheck_v1.py     — 13 unit tests on Q2/Q7/Q22 + edge cases
  validate_outputs.py     — JSON-schema validation (delegates to v0)
  COMPARE_v0_v1_fitcheck.md  — 2×2 grid + falsifiability scoreboard
  README.md               — this file
```

## Inputs (all inherited)

| Input | Location |
|---|---|
| Chunks | `audits/puzzlebook35/corpus/puzzlebook_raw_chunks_v1.jsonl` |
| Questions | `audits/puzzlebook35/audit_v0.questions.jsonl` |
| v0 retrieval | `runs/<DATE>_v0_baseline.jsonl` (TF-IDF) |
| v1 retrieval | `runs/<DATE>_v1_bm25.jsonl` (BM25) |

## Outputs

| File | Content |
|---|---|
| `runs/<DATE>_v0_fitchk1.jsonl` | TF-IDF retrieval × v1 fit_check |
| `runs/<DATE>_v1_fitchk1.jsonl` | BM25 retrieval × v1 fit_check |
| `manifests/<DATE>_v0_fitchk1.manifest.json` | Manifest with `fit_check.version: v1_hybrid` |
| `manifests/<DATE>_v1_fitchk1.manifest.json` | Same for BM25 lineage |

## Run

```bash
.venv/bin/python audits/puzzlebook35/fitcheck_v1/pipeline.py --run-date 2026-05-02
```

Expected stdout:

```
Re-scored 2 runs through fit_check v1:
  2026-05-02_v0_fitchk1:
    outcomes: hit=30  fit_refuse=5  given_up=0
    fit_dist: match=29  partial=1  mismatch=5  skipped=0
  2026-05-02_v1_fitchk1:
    outcomes: hit=30  fit_refuse=5  given_up=0
    fit_dist: match=30  partial=0  mismatch=5  skipped=0
```

## Validate

```bash
.venv/bin/python audits/puzzlebook35/fitcheck_v1/validate_outputs.py
```

Reuses `baseline_v0/validate_outputs.py` schemas; locates the latest
`*_v0_fitchk1.jsonl` and `*_v1_fitchk1.jsonl` and validates both.

## Tests

```bash
cd audits/puzzlebook35/fitcheck_v1 && python -m unittest test_fitcheck_v1 -v
```

13 tests pinning Q2 known-hit, Q22 not-in-corpus, Q7 ambiguity, plus
edge cases for alignment floor, OOS gate, count+noun co-occurrence,
and trigger-window conjunctions.

## Determinism

Two consecutive pipeline runs produce byte-identical run JSONLs
(verified during development with `sha256sum`).

## Falsifiability

Pre-registered in `baseline_v0/FITCHECK_V1_DESIGN.md` (commit `595f010`):
6 metrics. Result: 5 PASS, 1 FAIL. Failed metric (`match` rate ≤ 50%)
was misspecified — see `COMPARE_v0_v1_fitcheck.md` §"About metric #1"
for why it has been retired and what the v2 replacement looks like.

Pre-registration rule: "≥2 fail → design wrong, revisit before iterating".
v1 ships at 1 fail.

## Key results

- **All three pilot audit rows preserved their predicted outcomes**
  through the v0 → v1 fit_check change:
  - Q2 (Q-known-hit) still `match → hit`.
  - Q7 (ambiguity_test) still `mismatch → fit_refuse`, now via
    contextual trigger-window failure instead of `intent=who skipped`
    accident.
  - Q22 (not_in_corpus_test) still `mismatch → fit_refuse`.
- **4 of 10 NOTES §4 false-hits correctly flipped** to `fit_refuse` /
  `partial` (Q6 partial; Q20, Q26, Q31 fit_refuse via OOS).
- **`who` regex 100% match rate collapsed to 0%** on the only
  intent=who question (Q7).
- **fit_check v1 is almost retrieval-independent at the outcome level**
  — same 30/5 hit/refuse split across TF-IDF and BM25 retrievals,
  with one cell-level partial vs match difference on Q6.

## What this baseline does NOT cover

See `COMPARE_v0_v1_fitcheck.md` §"What v1 does NOT fix" for the four
unaddressed failure classes recorded as v2 candidates: trigger-gate
for why/how alignment, generic-chunk dominance via question-specific
noun anchoring, multi-chunk reasoning, and the embedding-retrieval
axis (blocked on HF network access).
