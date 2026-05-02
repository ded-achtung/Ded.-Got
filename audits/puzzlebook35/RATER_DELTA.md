# RATER_DELTA.md — first inter-rater signal on puzzlebook35 pilots

## 1. Что это

В рабочей директории на момент старта части (1) уже лежали Q22 и Q7
audit-строки и run-записи, написанные другой инстанцией Claude (предыдущая
сессия / параллельный контейнер — точно не установить). Это методологически
интересный артефакт: оба rater — Claude, читали те же документы Pack v0.2.1,
но prompt-контексты различны.

Не «настоящий второй rater» (нет независимости от модели), но первая
дисперсия выборов на проекте, которую стоит зафиксировать вместо silent
overwrite.

Caveat: provenance не верифицирована; считаем как «другая инстанция той же
модели» в максимально консервативной формулировке.

## 2. Q22 — где разошлись

Question: «Когда была впервые выпущена книга „Programming Puzzles, Python
Edition“?»

Согласие на: `answerable_in_corpus=false`, `failure_mode_audit=not_in_corpus`,
`evidence_verdict=underdetermined`, `action_expected_alignment=full`,
`final_outcome=fit_refuse`.

Расхождение:

| Поле | Other instance | This instance | Анализ |
|---|---|---|---|
| `audit_confidence` | `high` | планировал `medium` | **Their choice is stronger.** They support `high` через regex `\b(19\|20)\d{2}\b` по всем 27 чанкам с 0 хитов, плюс `version_numbers_treated_as_years: false` явно фиксирует, что 3.10 не считается годом. Это machine-verifiable exhaustiveness, что усиливает дисциплину rule 4.1. |
| `forbidden_evidence` count | 5 | 6 | Тривиально, тот же coverage. |
| `fit_details.version_numbers_*` | заполнено | планировал не заполнять | Their добавление эксплицитного "decoy class detected and rejected" — методологически чище. |

**Урок:** Pack rule 4.1 (`not_in_corpus + audit_confidence=high` требует
`exhaustiveness=high`) underspecifies *чем* подтверждается exhaustiveness.
Other instance ввели **machine-verifiable check** как валидацию. Это кандидат
на formalization в RVP — добавить рекомендацию «for `when`/`how_many` /
числовых intent, exhaustiveness=high SHOULD include programmatic check
(regex / numeric-presence) over the corpus, not only manual queries_tried».

## 3. Q7 — где разошлись (содержательно)

Question: «Кто является автором задач в книге?»

Согласие на: `answerable_in_corpus=false`, `evidence_verdict=underdetermined`,
`failure_mode_audit=ambiguous_question`, четыре интерпретации (book-author,
per-task source, translator, publisher).

Расхождение:

| Поле | Other instance | This instance | Анализ |
|---|---|---|---|
| `ambiguity.to_auditor` | `false` | планировал `true` | **Genuine disagreement.** См. §3.1. |
| `final_outcome` | `given_up` | планировал `fit_refuse` | **Their model более gradient.** См. §3.2. |
| `fit_status` | `partial` | планировал `mismatch` | Связано с предыдущим. |
| `action_expected_alignment` | `partial` | планировал `full` | Зависит от модели outcome. См. §3.3. |
| `possible_interpretations` format | structured (PI1–PI4 ids + interp text) | full-text-only список | Their format чище для machine reading. |
| `interpretation_relations` | 5 связей через PI-ids | 4 связи через full-text refs | Их ID-based reference — лучше при сериализации. |

### 3.1. `ambiguity.to_auditor` — semantic split

Other instance reads it as: *«can the auditor name and structurally
articulate the possibilities?»* — да, 4 интерпретации артикулированы →
`false`.

This instance reads it as: *«can the auditor select THE answer
without external clarification from the user?»* — нет, между
интерпретациями нет правильной по корпусу → `true`.

**Pack §3 не выбирает между этими двумя чтениями.** Это
underspecification field в Pack v0.2.1. Кандидат на clarification в RVP:
формализовать `to_auditor` как «can the auditor commit to a single
interpretation» (semantic intuition this instance) ИЛИ как «can the
auditor enumerate the interpretation set» (semantic intuition other
instance).

### 3.2. `given_up` vs `fit_refuse`, и `fit_status: partial`

Other instance моделирует system как 2-step:
- step 1: retrieval surfaces pb_intro_007 (URL with username "MatWhiteside")
- step 2: fit_check finds person-like string but no authorship relation
- result: given_up (no clear refuse path; system stalled mid-process)

This instance моделировал бы system как 1-step:
- step 1: retrieval + fit_check, fit_status=mismatch (no person entity in
  authorship relation)
- result: fit_refuse (clean refuse)

**Their model отражает реальность точнее**, потому что:
- В реальном retrieval URL с username действительно поднимется
  как кандидат
- `fit_status=partial` — graded match (есть person-like, нет relation),
  более выразительно чем бинарное mismatch
- `given_up` corresponds to «I tried and the chain didn't close»,
  что точнее описывает behaviour для ambiguous case

This instance бы пропустил эту nuance.

### 3.3. `action_expected_alignment` — partial vs full

Other instance: `partial` — system gave_up без активного запроса
clarification, expected behaviour для ambiguous включал бы request for
clarification, поэтому not full.

This instance планировал: `full` — under any interpretation the
right action was refuse, и system refused, поэтому full.

**Это снова underspecification field.** Что считать «expected action»
для `failure_mode_audit=ambiguous_question`?
- Refuse silently: minimum acceptable
- Refuse with explanation: better
- Ask clarification: ideal

Если expected = «refuse», то обе сессии full. Если expected = «ask
clarification», то given_up — partial (тщательно close), fit_refuse —
тоже partial (silent refuse).

Это **второй underspecification field** для action_expected_alignment,
который патч должен закрыть. Третий ниже.

## 4. Совокупный сигнал

На двух pilot rows одна inter-rater divergence (Q7) дала **3
underspecification points в Pack v0.2.1**:

1. `exhaustiveness=high` — не специфицировано, чем подтверждается
   (manual queries vs programmatic check) → patch для RVP rule 4.1.
2. `ambiguity.to_auditor` — два чтения semantic'а, оба защитимы → patch
   для RVP §3.
3. `action_expected_alignment` для `ambiguous_question` outcome —
   underspecified, что считать expected action → patch уже планировался,
   но Q7 даёт конкретное напряжение для формализации.

Это **в 3 раза больше методологического сигнала**, чем self-audit одного
Q-known-hit. Inter-rater divergence — не шум, а основной механизм
обнаружения underspecification в audit framework.

## 5. Какой rater сильнее

Не доминирует один. Q22 — other instance стронгер (machine-verifiable
exhaustiveness). Q7 — other instance стронгер на fit/outcome model
(graded fit, given_up vs binary refuse), this instance стронгер на
to_auditor argument (irreducible polysemy vs articulability).

Это здоровый сигнал: divergence не сводится к «один rater хуже». Если бы
сводился, это означало бы, что framework на самом деле однозначен и
один из нас просто плохо его читает. Ровная divergence означает, что
framework underspecified, и это эмпирический сигнал для patch'а.

## 6. История

- **v0, 2 May 2026.** Зафиксирован первый inter-rater data point на
  проекте. Two LLM instances (both Claude), partial independence через
  разные prompt контексты. Q22: agreement on diagnosis, divergence on
  audit_confidence justification. Q7: agreement on ambiguity, divergence
  on outcome model и to_auditor semantics. Generated 3 underspecification
  candidates for RVP patch.
