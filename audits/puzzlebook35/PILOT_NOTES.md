# PILOT_NOTES.md — puzzlebook35 audit through parts (1)+(2)+(3)

## 0. Что в этой папке после трёх частей

| Файл | Содержание | Происхождение |
|---|---|---|
| `audit_v0.questions.jsonl` | 35 вопросов | this instance |
| `audit_v0.chunks.jsonl` | 27 чанков (paraphrased) | this instance |
| `audit_v0.manual.jsonl` | 3 audit-строки: Q2, Q22, Q7 | Q2 — this; Q22, Q7 — другая инстанция Claude |
| `runs/2026-05-02_v3.20_puzzlebook_pilot_simulated.jsonl` | run records для Q2, Q22, Q7 | те же rater'ы соответственно |
| `manifests/2026-05-02_v3.20_puzzlebook_pilot_simulated.manifest.json` | manifest | this instance |
| `pre_flight_sanity_check.jsonl` | 35 строк preflight (this) | this instance |
| `audit_v0.preflight.jsonl` | 35 строк preflight (theirs) | другая инстанция |
| `RVP_PATCH_action_expected_alignment.md` | patch proposal | другая инстанция |
| `RATER_DELTA.md` | inter-rater сравнение по Q22, Q7 | this instance |
| `PILOT_NOTES.md` | этот файл | this instance |

## 1. Главное наблюдение этой итерации — multi-instance leftover state

В трёх случаях подряд я обнаружил, что **другая инстанция Claude уже
сделала часть работы**: Q22 audit row, Q7 audit row, RVP patch,
preflight JSONL. Не silent overwrite — каждый раз я читал, сравнивал,
оставлял существующий артефакт и документировал свою альтернативную
версию там, где была methodological substance.

Это **первый реальный inter-rater signal** на проекте, хотя и не
полностью независимый (оба rater — Claude, оба читали те же документы
Pack v0.2.1, отличаются только prompt-контексты). Он дал больше
методологического сигнала, чем self-audit одного Q-known-hit.

## 2. Часть (1) — Q22 + Q7 пилоты: результат

**Q22 (`not_in_corpus` тест):** другая инстанция дала более сильную
версию — `audit_confidence=high` поддерживается **machine-verifiable
regex check** (`\b(19|20)\d{2}\b` → 0 хитов по всем 27 чанкам). Я
планировал `medium` на основании «LLM rater + simulated run». Их
подход усиливает дисциплину rule 4.1: exhaustiveness теперь
operationally checkable, а не только декларируется.

**Q7 (`ambiguous_question` тест):** реальное расхождение по трём полям
(`ambiguity.to_auditor`, `final_outcome`, `action_expected_alignment`).
Не один rater явно сильнее. Расхождение полностью документировано в
`RATER_DELTA.md` §3, и оно вскрыло **3 underspecification points** в
Pack v0.2.1.

**Вывод части (1):** stop-rule per Pack §12 формально выполнен (3
пилота сделаны). Но «3 пилота» означает теперь не «3 successful pilot
labellings одного rater», а «3 pilot labellings + 1 inter-rater
divergence». Второе богаче.

## 3. Часть (2) — pre-flight sanity check: результат

Сделан в **двух версиях** (другая инстанция написала свой preflight
параллельно). Я не сливал — рассогласование между двумя preflights
само есть signal.

### 3.1. Crosscheck двух preflights

Сравнение через python (см. внутри терминала):

- **Gold disagreements: 3/35** (Q31, Q34, Q35) — на пограничных
  questions с reasoning или ambiguity. Все три — defensible на обе
  стороны.
- **Support_mode disagreements: 6/35** — пять из них по тому же
  underspecification: Pack §9 enum для `gold_support_mode` =
  `single_chunk | multi_chunk_path | unknown`, но для not_in_corpus и
  ambiguous case «unknown» — единственное in-spec значение, теряющее
  информацию. Другая инстанция использовала out-of-spec метки
  (`"ambiguous"`, `"not_in_corpus"`); я держался enum'а.
- **Question_type face validation:** другая инстанция добавила поле
  `question_type_face_validates`, отсутствующее у меня. Они задемоутили
  **Q24 и Q28** на этом основании.

### 3.2. Q24 и Q28 demotions — реальная проблема

**Q24** (Морзе для "A"): paraphrased chunk pb_t09_001 содержит фразу
«morse_dict для букв a-z, цифр 0-9 и спецсимволов», но **не показывает
конкретно `'a': '.-'`**, хотя реальная книга показывает. На
paraphrased corpus ответ **не извлекаем**. Real corpus → answerable;
paraphrased corpus → not_answerable.

**Q28** (filter_palindromes на пустом списке): мой чанк показывает
примеры с непустым входом и пустым выходом, но **не пример с пустым
ВХОДОМ**. Реальная книга это тоже не показывает явно (примеры даны
для непустых списков). Это вопрос, ответ на который требует общего
понимания «filter возвращает пустой результат на пустом входе», что
inferable, но не явно gold-supported в чанке.

**Это конкретная инстанция риска, флагнутого в предыдущем PILOT_NOTES
§5 («paraphrased chunks vs raw chunks»). Не теоретический риск, а
эмпирически наблюдаемый — на 2 из 35 вопросов.**

### 3.3. Gold collisions — статистика

`pb_intro_003`: 4 questions (Q5, Q21, Q32, Q34)  
`pb_intro_004`: 3 questions (Q1, Q29, Q30)  
`pb_t01_001`: 3 questions (Q3, Q14, Q27)  
`pb_t09_001`: 3 questions (Q24, Q25, Q31)  

Это **не баг** — естественно, что на маленьком корпусе (27 чанков)
35 вопросов имеют пересечения по gold. Но при анализе результатов
нужно учитывать: модель, выучившая один из этих 4 чанков, получит
несбалансированное преимущество.

## 4. Часть (3) — RVP patch для action_expected_alignment

Patch написан другой инстанцией, прочитан мной целиком. Substance
sound:
- Enum `"full" | "partial" | "none" | "unknown"`
- Правильно работает на трёх pilot rows без переписывания
- Правильно идентифицирует, что field — manual audit, не release-gate
- Вставляется в Pack §3.2 + §6.1 + §9 минимально-инвазивно

**Моя единственная заметка по существу:** значение `"none"` я бы
переименовал в `"misaligned"`. В Pack-like контексте `"none"` читается
как «нет alignment / null», а реальная семантика — «противоположное
направление» (fabrication, over_refuse). Не critical; user может либо
оставить, либо сменить — substance proposal'а на этом не висит.

## 5. Underspecification points обнаруженные через пилоты + preflights

Сводная таблица того, что нужно адресовать в Pack до full 35 labeling:

| Gap | Откуда обнаружен | Patch написан? |
|---|---|---|
| 1. `action_expected_alignment` enum | Q22 + Q7 inter-rater | ✓ (есть proposal) |
| 2. `exhaustiveness=high` mechanism | Q22 inter-rater | not yet |
| 3. `ambiguity.to_auditor` semantics | Q7 inter-rater | not yet |
| 4. `gold_support_mode` enum для not_in_corpus / ambiguous | preflight inter-rater | not yet |
| 5. paraphrased vs raw chunks methodological gap | Q24, Q28 demotions | not yet (it's a project-wide decision, not a Pack patch) |
| 6. Pack §3.2 example Q22 contradicts pilot result | проявилось в (3) | discussed in patch §3.4 |

Из шести — один patch написан. Остальные пять — кандидаты на
follow-up patches или Pack v0.3.

## 6. Что ещё не делано и почему

**Не делано:**
- Full 35 labeling — Pack §13 запрещает до review
- Реальный baseline run — требует chunked PDF и retrieval pipeline
- Inter-rater agreement scoring — n=3 пилотов слишком мал
- Patch'и для underspecifications 2-6 — сделаны бы, но это уход в
  patch-spam без user review

**Stop-rule:** три части (1)+(2)+(3) выполнены. Pack §12 stop-rule
закрыт. Нужен твой review до full 35 labeling и/или до решения по
underspecifications 2-6.

## 7. Что давать на review (приоритет)

В порядке убывания методологической ценности:

1. **`RATER_DELTA.md`** — главный артефакт inter-rater сигнала.
   Содержит 3 underspecification points с конкретным material'ом.

2. **`audit_v0.manual.jsonl`** — три audit rows (Q2, Q22, Q7) под
   Pack v0.2.1 с разными rater'ами, готовы для подсчёта inter-rater
   agreement если/когда захочется.

3. **`RVP_PATCH_action_expected_alignment.md`** — proposal под одно из
   обнаруженных gap'ов. Принять/изменить/отклонить — на твоё решение.

4. **`pre_flight_sanity_check.jsonl` + `audit_v0.preflight.jsonl`** —
   две версии preflight; их diff показывает Q24/Q28 demotion (real
   problem с paraphrased chunks).

5. **Этот PILOT_NOTES.md §5** — table из 6 underspecifications, чтобы
   ты мог решить порядок обработки.

## 8. История

- **v0.2, 2 May 2026.** Расширен после выполнения частей (1)+(2)+(3).
  Зафиксированы три pilot rows (Q2, Q22, Q7), preflight в двух
  параллельных версиях, RVP patch для action_expected_alignment, и
  таблица из 6 underspecifications. Multi-instance leftover state стал
  методологической особенностью этой итерации; ни один из leftover
  artifact'ов не был silent overwritten.
- **v0, 2 May 2026.** Q-known-hit pilot на real corpus после смены
  с fluent Python на Whiteside puzzlebook.
