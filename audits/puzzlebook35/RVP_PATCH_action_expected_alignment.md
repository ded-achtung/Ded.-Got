# RVP_PATCH_action_expected_alignment.md

> **Status:** proposal awaiting decision. Не правит Pack без твоего согласия.
> **Reason:** gap, найденный при заполнении трёх pilot rows.
> **Scope:** не «новое поле» по §13, а **enum для существующего поля**.
> Применимо до старта full 35 labeling.

---

## 1. Что не работает в текущей версии

`action_expected_alignment` упоминается в Pack v0.2.1 как обязательное
поле audit-схемы, но его допустимый набор значений нигде не зафиксирован.

Что есть в Pack:
- §3.2, пример Q22 — использует `"partial"`.
- §9, schema list — поле перечислено, но без enum.

Что заполнял я в трёх pilots:
- Q2 (hit) — `"full"`.
- Q22 (not_in_corpus + fit_refuse) — `"full"`.
- Q7 (ambiguous + given_up) — `"partial"`.

Без формального enum'а массовая разметка 35 вопросов получит:
- inter-rater drift (разные раters выберут разные слова);
- неаудируемые отчёты (нельзя посчитать долю `full` vs `partial`,
  если значения свободные);
- сложности при потенциальной автоматизации этого поля по
  лестнице заслуженной динамики (`manual → auto-suggested → ...`).

---

## 2. Предлагаемый enum

```text
action_expected_alignment ∈ {"full", "partial", "none", "unknown"}
```

### Семантика

**`"full"`** — действие системы соответствовало ожидаемому действию
для данной ситуации.

Примеры:
- Hit с типизированной опорой: gold извлечён, синтез корректный,
  ответ опирается на gold (Q2 в этом pilot).
- Корректный `fit_refuse` при `not_in_corpus`: система не извлекла
  ложную опору, корректно отказалась (Q22 в этом pilot).
- Корректный `given_up` при честно нерешаемой задаче.

**`"partial"`** — действие достигло **части** ожидаемого ответа, но не
всей.

Примеры:
- Gold извлечён, но downstream synthesis упал → `final_outcome:
  generation_failed` с `action_expected_alignment: partial`.
- Отказ корректен, но по неверной причине (`fit_refuse` поставлен из-за
  `fit_mismatch` при том, что реальная причина — `not_in_corpus`).
- На ambiguous вопрос ideal action — попросить уточнение; система
  сделала `given_up` без вопроса; это не худшее (нет галлюцинации),
  но и не идеал → `partial` (Q7 в этом pilot).

**`"none"`** — действие не соответствовало ожидаемому.

Примеры:
- Система уверенно ответила, когда `not_in_corpus`-отказ был
  ожидаем → fabrication.
- Система отказалась, хотя достаточная опора была доступна (это
  пересекается с `failure_mode_audit: over_refuse`).
- На ambiguous вопрос система выбрала одну интерпретацию произвольно,
  без указания на неоднозначность.

**`"unknown"`** — недостаточно данных для суждения.

Примеры:
- Runtime metrics неполны (нет `final_outcome` или нет
  `retrieved_topk_chunk_ids`).
- Ambiguity на стороне auditor (`ambiguous_to_auditor: true`) — нельзя
  определить, какое действие было ожидаемо.

---

## 3. Куда в Pack это вставить

Минимальное изменение — три точки:

### §3.2, после примера Q22

Добавить одну строку перед закрывающим `}` примера или сразу после него:

```text
Допустимые значения action_expected_alignment: "full" | "partial" | "none" | "unknown".
Полная семантика — §6.1.
```

### §6 (Evidence verdict typology), новый подраздел §6.1

```markdown
## 6.1. Action expected alignment typology v0.2.2

`action_expected_alignment` фиксирует, насколько действие системы
соответствовало ожидаемому действию для ситуации.

[here paste the four definitions with examples from §2 above]
```

### §9 (Audit JSONL schema), в списке полей

Добавить в перечисление:

```text
- action_expected_alignment ∈ {"full" | "partial" | "none" | "unknown"} — см. §6.1.
```

---

## 4. Backward compatibility

Все три текущие pilot rows — валидны под предлагаемый enum:

| qid | использованное значение | валидно по enum |
|---|---|---|
| Q2 | `"full"` | да |
| Q22 | `"full"` | да |
| Q7 | `"partial"` | да |

Existing rows не нужно править.

---

## 5. Что патч НЕ делает

- Не меняет правила выбора между `failure_mode_audit` и
  `action_expected_alignment`. Это **разные** поля: первое — диагноз
  типа провала, второе — оценка действия системы. Они могут
  расходиться (например, `failure_mode_audit: not_in_corpus` +
  `action_expected_alignment: full`, как в Q22).
- Не делает поле release-gate. Остаётся manual audit field на
  `manual` уровне лестницы заслуженной динамики.
- Не предписывает агрегирование или порог (по §10 на n=35 это всё
  равно directional).

---

## 6. Вопрос к тебе

Принять как написано? Если да — патч в Pack v0.2.2 (1-line bump
version), и можно идти в full 35 labeling. Если нужны правки — какие?

Альтернативы, которые я рассматривал и отверг:

- **Двоичный enum `"aligned" | "misaligned"`.** Слишком грубо: не
  различает «частичный успех» и «полный провал». В Q7 это сразу
  становится проблемой.
- **Пятизначный enum с разделением `"none-fabrication"` и
  `"none-overrefuse"`.** Слишком тонко для v0; эти оттенки и так
  ловятся через `failure_mode_audit`.
- **Без enum, свободный текст с регекс-паттернами.** Не аудируется
  автоматически, плохо масштабируется на full 35.

Predпочтение — четырёхзначный, как выше.

---

## 7. История

- **v0, 2 May 2026.** Создан как proposal по итогам трёх pilot rows
  (Q2, Q22, Q7). Не правит Pack до твоего решения.
