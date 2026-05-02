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

## 6. Q2 на raw данных — Q-known-hit confirmation, gold + decoys предсказаны точно

Q2 (`Какие два внешних Python-модуля устанавливаются через pip согласно подготовке среды?`, `intent=what`, `pilot_role=Q-known-hit`) был написан как trivial case: ожидался clean hit на единственном chunk'е, содержащем оба имени модулей.

**Эмпирическое сопоставление с audit row на raw chunks:**

| предсказание audit row | проверка на raw | результат |
|---|---|---|
| gold = chunk с обоими именами `pygame` AND `PythonTurtle` | uniqueness check по corpus | **`pb_raw_09`** ("Внешние библиотеки Python") — единственный такой chunk в pp.12-38 ✓ |
| gold должен попасть в top-1 retrieval | v0 (TF-IDF), v1 (BM25) | **оба** поставили `pb_raw_09` в top-1 ✓ |
| forbidden_evidence pattern: «mentions of pip in install context without naming both specific modules» | uniqueness check по corpus | **`pb_raw_07`** ("Установка Python") — содержит `pip` без модулей, точно по паттерну ✓ |
| decoy chunk должен появиться в top-k как noise | v0, v1 top-k | оба retrievals поставили `pb_raw_07` в top-3 ✓ |

**Что подтвердилось:**

1. **Gold prediction.** Audit row предсказывал, что в корпусе существует уникальный chunk с relation+оба имени. На raw данных это true: только `pb_raw_09` содержит pair `(pygame, PythonTurtle)`. Никакой другой chunk не deserves gold по типизированным критериям audit row.

2. **Forbidden_evidence pattern preservation.** Audit row перечислил конкретные decoy patterns со ссылками на paraphrased chunks (`pb_intro_004`, `pb_intro_007`). На raw данных эти patterns воспроизводятся: `pb_raw_07` содержит ровно те самые `pip` install-mentions без module names. **Mapping paraphrased decoy → raw decoy preserved**: `pb_intro_004` ↔ `pb_raw_07` по типу noise.

3. **Retrieval поведение для Q-known-hit стабильно.** Когда вопрос имеет gold с unambiguous typed evidence, оба lexical retrieval методов (TF-IDF и BM25) возвращают gold top-1. `generic_chunk_dominance` failure mode здесь не срабатывает потому, что gold chunk сам имеет высокую specific vocabulary overlap с вопросом (`pygame`, `pythonturtle`, `pip`, `модул`, `установ` — не generic).

**Что Q2 confirmation даёт сверх Q22 и Q7:**

Q22 confirmation был about machine-verifiable check survival (year-regex). Q7 confirmation — about failure mode survival (regex over-match, chunk dominance). **Q2 — about positive case survival**: trivial well-formed audit row остаётся trivially correct после смены corpus material. Это базовый sanity property, без которого любые отрицательные подтверждения (Q22, Q7) не имели бы основания — мы бы не знали, что framework способен на корректные предсказания вообще.

**Audit row metadata refinement (recorded, not applied).** Q2 row написана с `audit_confidence: medium` потому, что rater also constructed questions/run AND chunks were paraphrased. Raw confirmation удаляет вторую часть caveat'а (chunks теперь real). Любая будущая re-labeling может рассматривать Q2 audit_confidence как retrospectively upgradable до `high` — но это meta-update, не unilateral.

**Замыкание цикла, теперь по трём rows.**

| qid | audit row prediction | raw confirmation |
|---|---|---|
| Q22 (`not_in_corpus_test`) | year-regex refuses on numeric noise | ✓ ASCII codes 80/114/111 в pb_raw_26 не match'ятся; fit_refuse корректен на двух retrievals |
| Q7 (`ambiguity_test`) | ambiguity → over-match на capitalized noise | ✓ 10 false names matched, lexical_pattern_overmatch failure mode эмпирически подтверждён |
| Q2 (`Q-known-hit`) | gold = single chunk с обоими module names; forbidden = pip-only decoys | ✓ pb_raw_09 unique gold, pb_raw_07 decoy в top-3 как предсказано |

Все три pilot audit rows, написанные на synthetic paraphrased data, **сохранили predictive power** на real raw data. Это первый эмпирический сигнал, что **audit JSONL как «язык, на котором ThoughtState говорит о своих провалах» (RVP §0) переносится между corpus realizations**, а не привязан к конкретным paraphrased chunk_id namespaces.

Это не означает, что любая будущая audit row будет переноситься так же. Но три из трёх — non-trivial baseline для следующего pilot'а.
