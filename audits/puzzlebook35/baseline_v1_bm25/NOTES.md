# baseline_v1_bm25 — empirical observations

Read this together with `COMPARE_v0_v1.md` (per-qid diff and false-hit
tracking) and with `baseline_v0/NOTES.md` (origin of the failure-mode
candidates checked here).

## Headline

`generic_chunk_dominance` is **not a TF-IDF artifact**. It survived a
controlled swap to BM25 Okapi (default k1=1.5, b=0.75 — the standard
mitigation for length bias in lexical retrieval). The dominance *chunk*
shifted (`pb_raw_05` Введение displaced from 7 → 3 top-1 slots), but
the slots were inherited by other long generic-vocabulary chunks
(`pb_raw_13` "И еще несколько…": 1 → 4; `pb_raw_23` Задача 9: 3 → 4).

Net effect on the 10 known false-hits from `baseline_v0/NOTES.md §4`:

- 1 fixed (Q6 — `pb_raw_06` parent intro → `pb_raw_08` correct subsection)
- 4 reshuffled but still wrong (Q9, Q11, Q20, Q31)
- 5 unchanged (Q13, Q16, Q26, Q29, Q34)
- 2 regressions on previously-correct picks (Q5, Q21 — see below)

## Two regressions worth noting

In `baseline_v0`, `pb_raw_05` (Введение) was top-1 for Q5 and Q21, and
in both cases it was the *correct* chunk (it genuinely contains "50
(+ несколько дополнительных) задач" for Q5, and discusses the
серьёзные/шуточные distinction for Q21).

BM25's length penalty pushed `pb_raw_05` out of top-1 for these,
choosing instead `pb_raw_13` (Q5) and `pb_raw_23` (Q21) — both wrong.

This is the dual face of `generic_chunk_dominance`: when the generic
chunk *is* answer-bearing, length-aware retrieval punishes it for
exactly the property that made it correct (broad vocabulary covering
multiple questions). Length normalization is not a free win.

## Q7 / Q22 across methods

`lexical_pattern_overmatch` (NOTES §5) holds in v1 unchanged: same
top-1 (`pb_raw_05`), same regex hits, same `match → hit`. The failure
mode is independent of retrieval method — it is purely a property of
the fit_check rule.

Q22's `fit_refuse` also holds: top-1 = `pb_raw_26` (Задача 12 ASCII
codes), year-regex correctly filters out the numeric noise. The Q22
audit-row prediction is now confirmed across two retrieval methods.

## What this means for next steps

1. **Embedding baseline (v2) is still the open question.** v0 → v1
   ruled out "TF-IDF-specific artifact". It did not rule out
   "lexical-retrieval-specific artifact". A semantic embedder may
   behave differently. Currently blocked by HuggingFace network; needs
   weights uploaded to `vendored_models/multilingual-e5-small/`.

2. **fit_check work is justified by v1 too.** Even with BM25, 31 of 35
   questions go `skipped → hit` without challenge. Aggregate outcomes
   are identical to v0.

3. **Refinement of NOTES §5 TODO #3:** when extending fit_check, the
   audit of existing regex over-match must come first. Q7's failure
   persists across retrieval; it is a fit_check problem, not a
   retrieval problem.

## Honest caveats

- The "false-hit" labels themselves are eye-pass best-guesses from
  `baseline_v0/NOTES.md §4`, not adjudicated rows. A more careful
  re-labeling could move the score (e.g., Q11's "correct chunk" is
  arguably "no single right top-1" given multi-chunk reasoning).
- BM25 default hyperparameters were not tuned. k1, b sweeps could
  shift the picture; out of scope for this baseline.
- The corpus is small (30 chunks). Conclusions about retrieval method
  behaviour at scale do not transfer from this baseline alone.
