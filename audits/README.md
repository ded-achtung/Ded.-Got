# audits/ — выгрузка работы по RVP v0.2.1 pilots

Архив содержит artifact'ы, построенные за одну сессию работы над audit
framework по проекту Retrieval Visibility Pack v0.2.1.

Источники, которые **не** включены в архив:
- сами документы Pack v0.2.1 (RETRIEVAL_VISIBILITY_PACK.md и др.) —
  они у тебя есть как inputs;
- PDF Уайтсайда (Python в задачах и упражнениях) — у тебя есть.

## Структура

```
audits/
  README.md                  ← этот файл
  fluent35/                  ← первый pilot, синтетический test bed
  puzzlebook35/              ← второй pilot, реальный корпус
```

## История двух benchmark'ов

**fluent35** — первая попытка. Я сконструировал и corpus (chunks под Fluent
Python ch1-2), и questions, и run, и audit. Q-known-hit на Q1 (FrenchDeck
methods). Результат: формат прошёл baseline-проверку, но обнаружилась
структурная проблема — confirmation bias, потому что rater и constructor
test bed — один агент. См. `fluent35/PILOT_NOTES.md` §2.

**puzzlebook35** — replacement после смены corpus. Реальный PDF Уайтсайда
pp.12-38 (вступление + первые 15 задач). 27 чанков (paraphrased для
copyright), 35 вопросов выведены из реального содержания. Сделаны три
пилота (Q2, Q22, Q7), pre-flight sanity check на 35 вопросах, RVP patch
для action_expected_alignment enum, RATER_DELTA с inter-rater
сравнением. См. `puzzlebook35/PILOT_NOTES.md`.

**puzzlebook35 канонический.** fluent35 оставлен как archaeological
record — он показал, **зачем** понадобился реальный корпус, и на нём
видна methodology evolution.

## Рекомендуемый порядок чтения

1. `puzzlebook35/PILOT_NOTES.md` — главный обзор того, что сделано и
   что осталось. §0 — карта файлов, §5 — таблица 6 underspecification
   points в Pack.
2. `puzzlebook35/RATER_DELTA.md` — inter-rater сигнал по Q22 и Q7
   (главный методологический результат сессии).
3. `puzzlebook35/RVP_PATCH_action_expected_alignment.md` — proposal на
   review.
4. `puzzlebook35/audit_v0.manual.jsonl` — три audit rows (Q2 от меня;
   Q22, Q7 от другой инстанции Claude — они отмечены как inter-rater
   data в RATER_DELTA).
5. `puzzlebook35/pre_flight_sanity_check.jsonl` +
   `audit_v0.preflight.jsonl` — две версии preflight'а; их diff
   показывает Q24/Q28 demotion (paraphrased chunks vs reality).
6. `fluent35/PILOT_NOTES.md` — для понимания, почему пришлось менять
   corpus.

## Multi-instance leftover state

В ходе сессии 4 раза подряд обнаруживалось, что другая инстанция Claude
уже выполнила часть назначенной работы (Q22, Q7, RVP patch, preflight).
Каждый раз вместо silent overwrite я документировал альтернативные
выборы. Это дало первый реальный inter-rater сигнал на проекте и,
неожиданно, оказалось основным источником методологического сигнала
этой сессии — больше, чем self-audit. Подробности — в
`puzzlebook35/RATER_DELTA.md` и `PILOT_NOTES.md` §1.

Caveat: оба rater — Claude, не полностью независимый источник. Но
prompt-контексты различны, что создаёт некоторую дисперсию.

## Что НЕ сделано (и почему)

- **Full 35 labeling.** Pack §13 запрещает до user review.
- **Реальный baseline run** на retrieval pipeline. Требует кода, не
  делается из сессии.
- **Patch'и для underspecifications 2-6** (см. PILOT_NOTES §5). Не
  написаны, чтобы не уходить в patch-spam без user direction.
- **Inter-rater agreement scoring.** n=3 пилотов слишком мал для
  numerical agreement.

## Статус

Pack §12 stop-rule после трёх пилотов формально закрыт. Дальше нужен
твой review.

— claude-opus-4-7, single LLM rater, 2 May 2026
