# COMPARE_v0_v1: TF-IDF cosine vs BM25 Okapi

**Controlled change:** retrieval scoring formula only. Same chunks
(`puzzlebook_raw_chunks_v1.jsonl`, SHA-256 unchanged), same questions,
same tokenizer (`lowercase + \b\w\w+\b`), same fit_check policy, same
top-k = 10, downstream-effective-k = 4.

## Aggregate

| Metric                          | v0 (TF-IDF) | v1 (BM25) |
|---------------------------------|-------------|-----------|
| `final_outcome=hit`             | 34          | 34        |
| `final_outcome=fit_refuse`      | 1           | 1         |
| `fit_status=match`              | 3           | 3         |
| `fit_status=mismatch`           | 1           | 1         |
| `fit_status=skipped`            | 31          | 31        |
| top-1 differs from v0           | —           | 8 / 35    |
| top-4 differs from v0           | —           | 29 / 35   |

Aggregate outcome counts are identical. **Per-qid retrieval differs in
8 of 35 cases at top-1, 29 of 35 at top-4** — significant reordering
without aggregate effect, because fit_check is too coarse to register it.

## Top-1 chunk dominance

How often each chunk appears as top-1 across the 35 questions:

| chunk_id   | v0 count | v1 count | section                                 |
|------------|----------|----------|-----------------------------------------|
| pb_raw_05  | **7**    | **3**    | Введение                                |
| pb_raw_11  | 2        | 2        | Нотация O большое                       |
| pb_raw_13  | 1        | **4**    | И еще несколько предварительных замечаний |
| pb_raw_23  | 3        | **4**    | Задача 9                                |
| pb_raw_09  | 2        | 3        | Подготовка среды / Внешние библиотеки   |
| pb_raw_26  | 3        | 3        | Задача 12 (ASCII)                       |
| pb_raw_07  | 2        | 2        | Подготовка среды / Установка Python     |

Observation: `pb_raw_05` (Введение) dominance dropped 7 → 3. **But the
slot was inherited primarily by `pb_raw_13` (1 → 4) and `pb_raw_23`
(3 → 4)**, both of which are still long generic-vocabulary chunks
(typing examples + numbered list; Задача 9 with code). The dominance
*chunk* shifted; the dominance *failure mode* did not disappear.

`pb_raw_11` (Нотация O большое, 1569 chars, prose+code) — unchanged.

## Per-qid top-1 deltas (only where v0 ≠ v1)

| qid | intent  | v0 top-1   | v1 top-1   | NOTES §4 false-hit? | v1 fixes it? |
|-----|---------|------------|------------|---------------------|---------------|
| Q5  | how_many | pb_raw_05 | pb_raw_13  | no (was correct in v0) | **regression** — `pb_raw_05` Введение genuinely contains "50 (+ несколько дополнительных) задач" |
| Q6  | what    | pb_raw_06  | pb_raw_08  | yes                 | **yes** — moved from "Подготовка среды" intro to "Редактор кода" subsection (correct) |
| Q9  | how     | pb_raw_05  | pb_raw_23  | yes                 | no — moved to "Задача 9", still wrong (correct = `pb_raw_12` Нотация Примеры) |
| Q11 | what    | pb_raw_21  | pb_raw_24  | yes                 | no — moved between two task chunks; question is multi-chunk reasoning, no single right top-1 |
| Q20 | what    | pb_raw_05  | pb_raw_13  | yes                 | no — generic-Введение → generic-И еще несколько; correct = `pb_raw_29` Задача 14 |
| Q21 | how     | pb_raw_05  | pb_raw_23  | no (was correct in v0) | **regression** — `pb_raw_05` Введение discusses both серьёзные and шуточные задачи; v1 picks Задача 9 instead |
| Q31 | how     | pb_raw_23  | pb_raw_09  | yes                 | no — both wrong-category (out-of-corpus решение); v1 even further off topic |
| Q35 | what    | pb_raw_21  | pb_raw_13  | no (debatable)      | unclear — Q35 itself ambiguous ("какая задача демонстрирует срезы") |

For 27 questions where v0 = v1 at top-1: stable across retrieval methods.

## NOTES §4 false-hits — what BM25 changed

| qid | v0 false-hit reason            | v1 outcome           | verdict |
|-----|--------------------------------|----------------------|---------|
| Q6  | parent intro picked over subsection | moved to correct subsection | **fixed** |
| Q9  | generic Введение picked        | moved to wrong task chunk | reshuffled, not fixed |
| Q11 | one task chunk picked; answer needs reasoning | different task chunk | reshuffled |
| Q13 | nominally relevant subsection picked over "не импортируйте" intro | unchanged | unchanged |
| Q16 | Нотация O picked over typing-list chunk | unchanged | unchanged |
| Q20 | generic Введение picked        | generic И-еще picked | reshuffled |
| Q26 | task picked instead of (out-of-corpus) решение | unchanged | unchanged |
| Q29 | generic Введение picked over Установка Python | unchanged | unchanged |
| Q31 | task picked instead of (out-of-corpus) решение | different wrong chunk | reshuffled |
| Q34 | Нотация O picked over Серьёзные intro | unchanged | unchanged |

**Score: 1 fixed (Q6), 4 reshuffled-still-wrong (Q9, Q11, Q20, Q31), 5 unchanged (Q13, Q16, Q26, Q29, Q34). Plus 2 regressions on questions that were *correct* in v0 (Q5, Q21).**

Net: BM25 fixed 1 known false-hit, reshuffled 4, left 5 untouched, broke 2 previously-correct picks. **Not a win for BM25 as a `generic_chunk_dominance` fix.**

## Q7 / Q22 — failure-mode confirmations across methods

| qid | failure mode (NOTES §5)         | v0  | v1  | persists? |
|-----|---------------------------------|-----|-----|------------|
| Q7  | `lexical_pattern_overmatch`     | match → hit (top-1 `pb_raw_05`, 10 false "names") | match → hit (same top-1, same regex hits) | **yes — across retrieval methods** |
| Q22 | year-regex correctly refuses on numeric noise | mismatch → fit_refuse (top-1 `pb_raw_26` ASCII codes) | mismatch → fit_refuse (same top-1) | **yes — Q22 audit-row prediction holds across methods** |

Both audit-row predictions independent of retrieval choice. The
machine-verifiable check survives the swap.

## Epistemic update (the point of running v1)

**Before v1:** open hypothesis was that `generic_chunk_dominance` could
be a TF-IDF artifact (length normalization + cosine on bag-of-words).
If true, the fix is "swap retrieval", not "build fit_check rules".

**After v1:** BM25 explicitly designed to mitigate length bias (k1=1.5
saturation, b=0.75 length penalty). It does shift `pb_raw_05` out of 4
top-1 slots, but the slots are taken by other generic chunks
(`pb_raw_13`, `pb_raw_23`), and 2 of those shifts are *regressions* on
previously-correct picks. The aggregate hit/refuse counts are identical;
fit_check is still the only line of defense for the 31 skipped intents.

Conclusion: **`generic_chunk_dominance` is NOT a TF-IDF-specific
artifact**. It survives a controlled swap to BM25. It is a property of
retrieval-without-semantics over a corpus where short generic prose
chunks share vocabulary with many questions.

This argues for the work proposed in NOTES §5:
1. Audit existing fit_check regexes for over-match (Q7 holds in v1 too).
2. Extend fit_check to cover `what`/`why`/`how` — without a
   semantic-aware alternative (embeddings), this is the next available
   defense.

It does **not** rule out that an embedding-based v2 could behave
differently. v2 (when weights become available) tests a separate axis
(semantic similarity), not just a different lexical scoring.

## Files compared

| File                                           | SHA-256 (head 16) |
|------------------------------------------------|-------------------|
| `runs/2026-05-02_v0_baseline.jsonl`           | (see manifest v0) |
| `runs/2026-05-02_v1_bm25.jsonl`               | (see manifest v1) |
| `corpus/puzzlebook_raw_chunks_v1.jsonl`       | shared (manifest both) |
