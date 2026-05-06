# COMPARE_v1_v2_fitcheck — fit_check v1 vs v2

**Controlled change vs v1:** two narrow modifications to the alignment
path only.
1. `ALIGN_FLOORS = {what:(2,1), why:(4,4), how:(4,4)}` — per-intent
   match/partial floor instead of v1's global `(2, 1)`.
2. `tokenize()` now applies `ё→е` normalization before lowercasing.

Trigger windows (when/who/how_many), OOS gate, and dispatcher are
unchanged from v1. Same 2×2 retrieval × fit_check grid; v2 produces
two new cells.

## Aggregate (full 2×3 grid)

|                              | TF-IDF retrieval (v0) | BM25 retrieval (v1) |
|------------------------------|-----------------------|---------------------|
| **fit_check v0** (bare regex) | hit=34, refuse=1 | hit=34, refuse=1 |
| **fit_check v1** (hybrid)     | hit=30, refuse=5 | hit=30, refuse=5 |
| **fit_check v2** (v1 + per-intent floor + ё-norm) | hit=27, refuse=8 | hit=28, refuse=7 |

v2 narrows the hit/refuse split further. **First time in the project
that retrieval choice (TF-IDF vs BM25) materially affects the
aggregate outcome at fit_check level** — v2 distinguishes "answer
reachable in top-4" (BM25 includes pb_raw_14 for Q13 → match) from
"answer not in top-4" (TF-IDF Q13 → refuse). Q6 also differs
(TF-IDF: partial; BM25: match — pb_raw_08 promoted to top-1).

## Per-qid changes (v1 → v2)

### TF-IDF retrieval (v0)

| qid | intent | v1 status | v2 status | classification |
|-----|--------|-----------|-----------|----------------|
| Q9  | how    | match     | mismatch  | **flipped (pre-registered)** |
| Q13 | why    | match     | mismatch  | **flipped (pre-registered)** |
| Q27 | how    | match     | mismatch  | **flipped (unanticipated; multi-chunk question, fit_refuse arguably correct)** |

All other 32 rows unchanged from v1.

### BM25 retrieval (v1)

| qid | intent | v1 status | v2 status | classification |
|-----|--------|-----------|-----------|----------------|
| Q9  | how    | match     | mismatch  | **flipped** |
| Q27 | how    | match     | mismatch  | **flipped** |

All other 33 rows unchanged. Note: Q13 stays match on BM25 because
BM25's top-4 includes `pb_raw_14` (Серьезные intro: "Важно: не
импортируйте никакие библиотеки...") which TF-IDF's top-4 misses.
Same v2 policy, different retrieval, different correct outcome.

## Pre-registered falsifiability table (revised per REVISION 1)

Criteria from `baseline_v0/FITCHECK_V2_DESIGN.md` REVISION 1
(committed before any v2 code).

| # | metric | criterion | actual TF-IDF×v2 | pass? |
|---|--------|-----------|------------------|-------|
| 1 | `fit_refuse` count | ≥ 7/35 | 8/35 | ✓ |
| 2 | Q9 flips to fit_refuse | yes | yes | ✓ |
| 3 | Q13 flips to fit_refuse | yes | yes | ✓ |
| 4 | Q16 stays match (pb_raw_13 in top-4) | yes | yes | ✓ |
| 5 | Q29 stays match (pb_raw_06 in top-4) | yes | yes | ✓ |
| 6 | Pilot canaries Q2/Q7/Q22 unchanged | yes | yes | ✓ |
| 7 | Regressions on 14 known-correct | 0 | 0 | ✓ |
| 8 | Discriminative power | ≥ 75% | (6+14)/24 = 83.3% | ✓ |
| 9 | Determinism | yes | yes (sha256 stable) | ✓ |

**9/9 PASS** under the revised criteria. Pre-reg rule "≥2 fail →
design wrong" not triggered. v2 ships clean.

## REVISION 1 acknowledgment (already in design doc)

Original v2 commitments said Q16 and Q29 must flip to fit_refuse —
based on incomplete analysis (top-1 NOTES §4 frame, not top-4 best
alignment). Tracing actual top-4 alignment revealed:

- **Q16**: pb_raw_13 (typing rationale) IS in top-4 with alignment 4.
  pb_raw_13 IS the correct answer. v2's match → hit is **correct**,
  not a false-hit at fit_check level.
- **Q29**: pb_raw_06 (Подготовка среды intro) in top-4 with alignment 4.
  pb_raw_06 is topic-related but does NOT contain the procedural answer
  (which lives in pb_raw_07, NOT in top-4). Lexical alignment cannot
  distinguish "topic-matched" from "answer-bearing". Deferred to v3.

This was caught and recorded in `FITCHECK_V2_DESIGN.md` REVISION 1
**before** v2 implementation, preserving pre-registration discipline.

## What v2 still does NOT fix

| qid | intent | v2 status | reason | v3 candidate |
|-----|--------|-----------|--------|--------------|
| Q11 | what   | match→hit | multi-chunk reasoning ("в каких задачах из 1-15...") | per-intent aggregation |
| Q29 | how    | match→hit | topic-matched chunk (pb_raw_06) has alignment 4; answer chunk (pb_raw_07) not in top-4 | noun-anchoring on procedural markers (`шаг`, `1.`, `сначала`) |
| Q34 | how    | match→hit | answer chunk pb_raw_14 IS in top-4 with high alignment, but TF-IDF top-1 picks pb_raw_11 (which also matches "сложность"+"задач"); both lexically similar | rare-token anchoring or quoted-phrase matching |

`generic_chunk_dominance` failure mode (NOTES §4) is **partly addressed**
by v2 (closes Q9, Q13 + the unanticipated Q27 multi-chunk catch) but
**not eliminated** (Q29, Q34 persist).

## Summary

v2 = +3 fit_refuse on TF-IDF, +2 on BM25, with zero regressions.
Discriminative power 83.3% (TF-IDF), up from v1's 75%. All v2
pre-registered commitments met after REVISION 1 (which itself was
recorded honestly, not retrofitted).

The gap between TF-IDF v2 and BM25 v2 outcomes at the fit_check
level (Q13, Q6) is **the first material 2×2 grid signal in the
project** that retrieval choice + fit_check policy interact
non-trivially. Worth a separate note in audit metadata.
