# baseline_v0 — empirical observations

These are NOT audit rows. They are notes for whoever runs the next pilot
(re-labeling of pilot audit rows on raw chunks), so that the eye-pass
findings here don't have to be rediscovered.

## Known limitation: 31/35 questions go skipped → hit

By scope of CC_TASK_BRIEF, fit_check covers only `intent ∈ {when, who, how_many}`.
The other 31 questions return `final_outcome=hit` without retrieval ever
being challenged. **Do not interpret 34/35 hit-rate as recall.** It is
"baseline did not refuse" — fundamentally weaker.

Before re-labeling pilot audit rows on raw chunks, decide one of:
1. Extend fit_check to cover {what, why, how} (at least `not_in_corpus`
   detection by section-path / page-range proxy), OR
2. Explicitly mark all 31 skipped→hit rows as "fit_check unverified" in
   any comparison artifact, so the comparison is between like-for-like.

## Q26: expected false-hit, not bug

Q26 (`Какое предлагаемое решение задачи 5 (get_longest_string)?`) is
flagged `not_in_corpus` in `audit_v0.preflight.jsonl` — solutions live
on later pages (pp.> 38), outside the active corpus.

In baseline_v0, Q26 returns `final_outcome=hit` with top-1 = `pb_raw_19`
(Задача 5 — задание, not решение). This is consistent with the brief's
scope (`intent=how → skipped → hit`), but it is a **false-hit relative
to pre-flight `not_in_corpus`**. Do not compare baseline_v0 Q26 with
pre-flight as if they should agree — they were measured against
different policies.

The same applies, in spirit, to Q31 (`решить задачу 9 без словаря` — the
"решение" is not in pp.12-38).

## Q22: first empirical support for the audit row's regex check

Q22 (`Когда была впервые выпущена книга «Programming Puzzles, Python
Edition»?`, `intent=when`, `pilot_role=not_in_corpus_test`) returned
`fit=mismatch → fit_refuse` correctly, even though TF-IDF top-1 was
`pb_raw_26` (Задача 12, ASCII), which is **rich in numeric content**
(80, 114, 111, … as ASCII codes).

The year-regex `\b(19|20)\d{2}\b` rejects all of these — none match the
year shape. This is the first empirical signal on raw chunks that the
machine-verifiable exhaustiveness check from the Q22 audit row
(see `audit_v0.manual.jsonl` Q22 forbidden_evidence) survives transfer
from paraphrased to raw chunks. One of the six underspecifications in
`PILOT_NOTES.md §5.1` just got real-data backing.

Worth re-reading when the pilot row re-labeling task starts.

## Eye-pass false-hits visible without re-labeling

From `sanity_check.py` output, top-1 chunks that look obviously wrong
relative to the question:

| qid  | intent  | top-1 picked            | likely correct chunk        | comment |
|------|---------|-------------------------|-----------------------------|---------|
| Q6   | what    | pb_raw_06 (Подг. среды) | pb_raw_08 (Редактор кода)   | TF-IDF picked parent intro, not subsection |
| Q9   | how     | pb_raw_05 (Введение)    | pb_raw_12 (Нотация Примеры) | generic chunk dominates |
| Q11  | what    | pb_raw_21 (Задача 7)    | n/a (reasoning across tasks)| question requires multi-chunk reasoning |
| Q13  | why     | pb_raw_09 (Внешние библ.)| pb_raw_14 (Серьезные intro)| answer "не импортируйте..." is in intro |
| Q16  | why     | pb_raw_11 (Нотация O)   | pb_raw_13 (И еще несколько) | typing rationale is in §4 of numbered list |
| Q20  | what    | pb_raw_05 (Введение)    | pb_raw_29 (Задача 14)       | generic chunk dominates |
| Q26  | how     | pb_raw_19 (Задача 5)    | n/a (решение out of corpus) | section right, content category wrong |
| Q29  | how     | pb_raw_05 (Введение)    | pb_raw_07 (Установка Python)| generic chunk dominates |
| Q31  | how     | pb_raw_23 (Задача 9)    | n/a (решение out of corpus) | section right, content category wrong |
| Q34  | how     | pb_raw_11 (Нотация O)   | pb_raw_14 (Серьезные intro) | "трудность возрастает" line is in intro |

Caveats:
- This is an eye-pass, not a labeled set. "Likely correct chunk" is
  the author's best guess from a 200-char excerpt; some of these may be
  defensible top-1 picks under a stricter reading.
- Pattern: short prose chunks (Введение `pb_raw_05`, Нотация `pb_raw_11`)
  win TF-IDF when a question's vocabulary partially matches them but
  the actual answer is in a more specific subsection. This is the
  expected weakness of bag-of-words against hierarchical corpora.
- Of the 35: ~9 likely false-hits by content + Q22 correctly refused
  + 25 plausible top-1's (some certain, some need full read).

Do not propagate these as ground truth into the next pilot. Use them
as a starting checklist when raw-chunk audit rows are constructed.

## 5. Q7 на raw данных — confirmation двух failure modes

Q7 (`who`/ambiguous) при baseline retrieval v0 на raw chunks дал `match → hit`. Top-4: pb_raw_05, pb_raw_11, pb_raw_04, pb_raw_13. Capitalized-token regex match'нул 10 «имён» (`Python`, `Всюду`, `Выглядит`, `Для`, `Добро`, `Если`, `Задачи`, `Знакомство`, `Или`, `Их`) — ни одного личного имени.

Подтверждены **две независимые failure modes** одновременно:

- `generic_chunk_dominance` — TF-IDF взял `pb_raw_05` (Введение, короткий generic prose) поверх любого specific chunk.
- `lexical_pattern_overmatch` — capitalized-token regex match'ит начала предложений после точки, любую заглавную лексическую единицу. fit_check включён, но настолько широк, что отказа не происходит при отсутствии answer-bearing material.

Эти две failure modes не рефайнменты друг друга — они независимы. На Q7 они сработали одновременно. На false-hits из §1 (Q6, Q9, Q13, Q16, Q20, Q29, Q34) сработала первая в одиночку, потому что для их intent'ов (`what`/`why`/`how`) fit_check skipped и второй некуда было сработать.

**Импликация для приоритезации работы (refinement of TODO #3 в §4):** расширение fit_check на skipped intent'ы без аудита текущих regex'ов на over-match даст false comfort. `who` regex был включён и не отказал — то же самое произойдёт с наивно реализованными `what`/`why`/`how` regex'ами. Аудит уже написанных правил — pre-requisite, не co-task.

**Связь с paraphrased pilot.** Q7 audit row (написана на paraphrased chunks другой инстанцией) предсказывала ambiguity и отсутствие authorship relation как причину для refuse. Raw retrieval это **подтверждает** через конкретную failure path: regex over-match. Audit row из синтетической эпохи проекта оказалась predictive по отношению к raw data — первое замыкание цикла «audit-as-language → empirical-event» на проекте.
