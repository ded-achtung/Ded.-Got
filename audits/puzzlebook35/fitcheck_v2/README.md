# fitcheck_v2 — per-intent alignment floor + ё-normalization

Implementation of `audits/puzzlebook35/baseline_v0/FITCHECK_V2_DESIGN.md`
(commit `bbd376a` for v1 of the design, REVISION 1 added in same doc).

Two narrow changes vs `fitcheck_v1`:

1. `ALIGN_FLOORS` — per-intent (match, partial) thresholds:
   ```python
   {"what": (2, 1), "why": (4, 4), "how": (4, 4)}
   ```
   `what` unchanged; `why`/`how` raised to (4, 4) — below floor =
   mismatch, no partial state.
2. `tokenize()` applies `ё→е` normalization before lowercasing
   (lossless for this corpus).

Trigger windows (when/who/how_many), OOS gate, and dispatcher are
imported and reused unchanged from v1.

## Layout

```
audits/puzzlebook35/fitcheck_v2/
  fitcheck_v2.py             — overrides v1 tokenize + alignment
  pipeline.py                — re-scores both retrievals through v2
  test_fitcheck_v2.py        — 12 tests (4 flips, 4 no-regression, 3 canaries, 1 ё-norm)
  validate_outputs.py        — schema validation for v2 outputs
  COMPARE_v1_v2_fitcheck.md  — diff vs v1, falsifiability scoreboard
  README.md                  — this file
```

## Inputs (inherited from baseline_v0 / fitcheck_v1)

| Input | Location |
|---|---|
| Chunks | `audits/puzzlebook35/corpus/puzzlebook_raw_chunks_v1.jsonl` |
| Questions | `audits/puzzlebook35/audit_v0.questions.jsonl` |
| v0 retrieval (TF-IDF) | `runs/<DATE>_v0_baseline.jsonl` |
| v1 retrieval (BM25) | `runs/<DATE>_v1_bm25.jsonl` |

## Outputs

| File | Content |
|---|---|
| `runs/<DATE>_v0_fitchk2.jsonl` | TF-IDF retrieval × v2 fit_check |
| `runs/<DATE>_v1_fitchk2.jsonl` | BM25 retrieval × v2 fit_check |
| `manifests/<DATE>_v0_fitchk2.manifest.json` | with `fit_check.version: v2_per_intent_floor` |
| `manifests/<DATE>_v1_fitchk2.manifest.json` | same for BM25 lineage |

## Run

```bash
.venv/bin/python audits/puzzlebook35/fitcheck_v2/pipeline.py --run-date 2026-05-02
```

Expected stdout:

```
Re-scored 2 runs through fit_check v2:
  2026-05-02_v0_fitchk2:
    outcomes: hit=27  fit_refuse=8  given_up=0
    fit_dist: match=26  partial=1  mismatch=8  skipped=0
  2026-05-02_v1_fitchk2:
    outcomes: hit=28  fit_refuse=7  given_up=0
    fit_dist: match=28  partial=0  mismatch=7  skipped=0
```

## Validate

```bash
.venv/bin/python audits/puzzlebook35/fitcheck_v2/validate_outputs.py
```

## Tests

```bash
cd audits/puzzlebook35/fitcheck_v2 && python -m unittest test_fitcheck_v2 -v
```

12 tests pinning the pre-registered behaviour.

## Determinism

Two consecutive runs produce byte-identical JSONLs.

## Falsifiability — 9/9 PASS

See `COMPARE_v1_v2_fitcheck.md` §"Pre-registered falsifiability table".
All revised criteria met.

## Key results

- **+3 fit_refuse on TF-IDF, +2 on BM25** vs v1.
- **Zero regressions on 14 known-correct hits.**
- **Q9 and Q13 flip to fit_refuse** as pre-registered (after REVISION 1).
- **Q27 unanticipated flip** — multi-chunk question; fit_refuse arguably
  correct (single chunk can't compare two functions).
- **First retrieval-policy interaction in the project**: Q13 differs
  between TF-IDF×v2 (refuse) and BM25×v2 (match), because BM25's
  top-4 includes the answer chunk pb_raw_14 that TF-IDF misses. Same
  v2 fit_check, different correct outcomes.
- **Discriminative power 83.3%** on the 24-row labeled set (v1 was 75%).

## What v2 still does NOT fix (deferred to v3)

- **Q11** — multi-chunk reasoning across all tasks 1-15.
- **Q29** — answer chunk pb_raw_07 not reachable in top-4; pb_raw_06
  (topic-related but not answer-bearing) gives high alignment.
- **Q34** — both pb_raw_11 (top-1 wrong) and pb_raw_14 (right answer in
  top-4) score similarly on lexical alignment; rare-token anchoring
  needed.

The embedding retrieval axis (would resolve some of Q29/Q34 via
semantic similarity) remains blocked on HuggingFace network access.
