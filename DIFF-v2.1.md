# Document Diff v2.1

Статус: **draft**. Точечные правки к существующим документам на основе fact-checked наблюдений из экосистемы.

**Принцип правок:** «меньше триумфа, больше контрактов и ограничений». Каждый пункт — либо добавление осторожной формулировки, либо усиление существующего ограничения. Ни один пункт не расширяет scope 0.1.

Этот документ — proposal для PR, не финальная версия. После review применяется как batch.

---

## 1. Честная преамбула

Во всех документах, где упоминается экосистема, тон должен быть **наблюдательным**, не триумфальным. Конкретно:

**Было:**
> «Экосистема wallpaper-daemons на Wayland нестабильна» (RECON.md §2.1).

**Остаётся** (уже корректно).

**Было (гипотетическое):** формулировки типа «мы решаем проблему, которую никто не решил», «это меняет всё», «flagship feature».

**Становится:** «наблюдаем паттерн X, делаем Y с учётом этого». Без «поэтому мы победим».

---

## 2. Факты из экосистемы, которые усиливают существующие решения

Ни один из пунктов не требует изменения scope 0.1 из CHARTER-0.1.md. Все они — **доказательства в пользу** уже принятых решений.

### 2.1. hyprpaper v0.8.0 — complete rewrite, конфиги сломаны

**Подтверждение:** [hyprwm/hyprpaper releases](https://github.com/hyprwm/hyprpaper/releases/tag/v0.8.0), October 2025. Release note дословно: «This is a complete rewrite of hyprpaper into hyprtoolkit. Please note configs are broken and much simplified». Hyprland 0.53 требует hyprpaper 0.8.0.

**Следствие:** подтверждает CHARTER-0.1 §10 («не обещаем обратную совместимость IPC до 1.0, breaking changes ожидаемы и документируются в CHANGELOG»). Наш подход — лучше, чем в hyprpaper: breaking changes только **до** 1.0, после 1.0 — freeze.

**Правка в CHARTER-0.1.md §10:**

Добавить уточнение в конец пункта «Не обещаем обратную совместимость IPC до 1.0»:

> После 1.0 — IPC и config freeze, breaking changes только через major version bump (2.0). Это отличается от подхода некоторых соседних проектов, где complete rewrites случаются на минорных версиях. Мы сознательно принимаем более консервативный подход.

**Без триумфа.** Просто factual statement.

### 2.2. swww → awww rename, `wpaperd-ipc` как отдельный crate

**Подтверждение:** `wpaperd-ipc` на crates.io существует как standalone crate (1.0.0, April 2024, 2151 downloads). Паттерн «IPC types как отдельная библиотека» доказан.

**Следствие:** для нашего IPC это **хороший pattern**, но для 0.1 — **не обязательный**. В 0.1 IPC types живут в `wpe-ipc` crate (внутренний). Выделение в public `wpe-ipc-types` для third-party consumers — возможная задача для 1.0.

**Правка в SKELETON.md §2:**

Добавить к списку не-в-skeleton crate'ов:

> `wpe-ipc-types` — опциональный public crate с IPC type definitions для third-party tools. **Не в 0.1**. Рассматривается в 1.0 после IPC freeze.

Осторожная формулировка: «рассматривается», не «будет сделан».

### 2.3. niri `place-within-backdrop` — compositor-specific behavior

**Подтверждение:** [niri wiki Configuration Layer Rules](https://github.com/niri-wm/niri/wiki/Configuration), niri v25.05+. Compositor имеет separate background per workspace, wallpaper tools могут быть «placed within backdrop» через layer-rule с namespace matching.

**Следствие:** wlroots ≠ wlroots. Разные композиторы обращаются с layer-shell wallpaper по-разному. niri даже поддерживает **два wallpaper tools одновременно** (один для backdrop, один для обычных workspaces).

**Правка в RUNTIME.md §10 (Wayland Integration Contract):**

Добавить новый подраздел:

```markdown
### Compositor-specific observations

Layer-shell wallpaper protocol стандартен, но compositor-specific behavior
существует. Observed cases (не исчерпывающий список):

- **niri**: separate background per workspace. Поддерживает `place-within-backdrop`
  layer-rule для wallpaper tools. Может запускать два wallpaper tools одновременно
  (backdrop + workspace).
- **Hyprland**: standard layer-shell behavior, но hyprpaper использует свой IPC
  через hyprctl, не Wayland protocol.
- **Sway, Wayfire, labwc, river**: стандартный layer-shell behavior.

**Что это значит для нас в 0.1:**

1. Используем стабильное layer-shell namespace (`wpe-wallpaper`). Документируем.
   Пользователи niri могут использовать наш namespace в своих layer-rules.
2. **Не** пытаемся детектить конкретный compositor и менять поведение.
   В 0.1 — один код path для всех wlroots-based compositors.
3. Если возникнет compositor-specific issue — документируем в
   `docs/known-issues.md`, не добавляем код path.

Compositor-aware behavior (если станет нужно) — предмет отдельного charter-change
после 0.1 stable. В 0.1 это **explicitly out of scope**.
```

**Осторожная формулировка.** Факт записан, но код не добавляется.

### 2.4. Treeland wallpaper color protocol

**Подтверждение:** [wayland.app/protocols/treeland-wallpaper-color-v1](https://wayland.app/protocols/treeland-wallpaper-color-v1). Treeland — compositor DDE (Deepin Desktop Environment) имеет собственные wallpaper-related protocol extensions.

**Следствие:** palette integration на уровне Wayland protocol — **существует** в экосистеме, но это **compositor-specific**, не cross-compositor standard.

**Правка в PLATFORM.md §5 (Theme Integration):**

Добавить наблюдение в конец раздела:

```markdown
### Compositor-specific palette protocols (observational)

Существуют compositor-specific Wayland protocols для palette integration
(например, `treeland-wallpaper-color-v1` в Treeland). Это не cross-compositor
standard, это per-compositor extension.

**Что это значит для нас:**

- Наш palette layer (0.3) — через filesystem + DBus, не через Wayland protocol.
- Если какой-то compositor-specific protocol станет стандартом (или популярным) —
  рассмотрим integration в отдельном minor релизе после 0.3.
- В 0.3 **не** имплементим treeland-specific protocol. Слишком узкая поддержка.

Это соответствует принципу PLATFORM.md §1: Platform Core самодостаточна.
Compositor-specific hooks — опциональны и не в Core.
```

### 2.5. `wpaperd` как архитектурный ориентир

**Подтверждение:** wpaperd 1.0.1 (crates.io). Modern wallpaper daemon, Rust, OpenGL ES, hardware-accelerated transitions, TOML config с hot reload, CLI через `wpaperctl`, IPC types в отдельном crate. **License: GPL-3.0+**.

**Следствие:** wpaperd — хороший референс для паттернов (TOML config, hot reload, separate CLI). **Но:** GPL-3.0 incompatible с нашей MIT/Apache-2.0 licensing policy. Мы **не** можем use wpaperd code directly. Только learn from patterns.

**Правка в PROJECT.md §3 — добавить D10:**

```markdown
### D10. Licensing policy

Наш код — dual-licensed MIT / Apache-2.0. Это исключает ряд source-code references:

- `wpaperd` (GPL-3.0+) — изучаем как patterns reference, не копируем код.
- `linux-wallpaperengine` (GPL-3.0) — то же. Adapter в Фазе II общается через
  IPC/subprocess boundary, не linking.
- `mpvpaper` (GPL-3.0) — то же.

Это не делает соседние проекты «хуже» — это техническое ограничение
distribution flexibility. Наш подход (MIT/Apache) позволяет включение
в проекты с любой совместимой лицензией.

Зависимости: только crates с compatible licenses (см. `deny.toml`).
```

**Правка в RECON.md §9 (Libraries):**

Добавить примечание к списку проектов:

```markdown
**License note.** wpaperd, linux-wallpaperengine, mpvpaper, hidamari — все GPL-3.0+.
Мы изучаем их как architectural references, не используем как dependencies.
Наш код — MIT/Apache-2.0.
```

### 2.6. hyprpaper complete rewrite подтверждает value «migration stability»

**Что это значит для нас** (не приписывая себе готовую фичу):

CHARTER-0.1.md §2 не содержит «migration tools». Это сознательно. Но diagnostic system (CHARTER-0.1.md §8) должна понимать **типичные миграционные сценарии** для troubleshooting.

**Правка в CHARTER-0.1.md §8:**

Добавить новый пункт в конец секции:

```markdown
### Migration awareness (не migration tools)

Первый пользователь 0.1 — часто refugee из `hyprpaper`/`swww`/`awww`. Diagnostic
system должна распознавать common patterns и давать actionable suggestions.

Пример:

```
[W050] hyprpaper config detected
  Location: ~/.config/hypr/hyprpaper.conf
  Info:     We are not hyprpaper-compatible. Our config format differs.
  Suggestion: See docs/migration/from-hyprpaper.md for equivalent configuration.
```

**Что это НЕ:** automated migration tool, import format converter, compat layer.

**Что это:** аккуратное diagnostic, которое признаёт, что пользователь приходит
откуда-то, и помогает сориентироваться. Ничего больше.

Migration tool как first-class feature — **не в 0.1**. Возможно в 0.3+, если
будут чёткие паттерны и user demand. Сейчас — только awareness.
```

---

## 3. Правки, которых **не делаем**

Для полноты — явный список того, что я **не** добавляю, несмотря на искушение.

### 3.1. Не добавляем CompositorProfile

Да, niri и Treeland показывают compositor-specific behavior. Но:
- Система профилей композиторов = дополнительная сложность.
- В 0.1 можно обойтись документированием known-issues.
- Если будет реальная boilerplate необходимость — отдельный charter-change после 0.1.

### 3.2. Не добавляем adapter layer в 0.1

PROJECT.md D9 и CHARTER-0.1 §4 запрещают. Несмотря на наличие `mpvpaper`, `wpaperd`, `linux-wallpaperengine` как живых проектов — adapter layer остаётся Фазой II.

### 3.3. Не делаем `linux-wallpaperengine` adapter «flagship»

PROJECT.md §1 называет его «главной новой фичей Фазы II». Это **не** «flagship promise». Это «главная цель Фазы II, когда Фаза II начнётся».

Оставляю формулировку как есть.

### 3.4. Не добавляем wallpaper cycling (slideshow) в 0.1

wpaperd имеет cycling (duration-based wallpaper rotation). Мы **не** имеем в 0.1. Это может быть в 0.4 (через activation rules) или не быть вовсе.

### 3.5. Не добавляем palette integration через Wayland protocol

Treeland protocol существует. Мы используем filesystem + DBus (традиционный путь). В 0.3.

### 3.6. Не называем себя «stability-first alternative»

Искушение маркетинга. Наш CHARTER-0.1 §10 говорит «не обещаем backward compat до 1.0». Называть себя stability-first **до** того, как у нас есть 1.0 — преждевременно.

В README через 6 месяцев после 1.0 — можно. Сейчас — нет.

---

## 4. Где внутренняя противоречивость обнаружена

При написании этого diff'а всплыло **одно реальное противоречие** в существующих документах:

### Противоречие: license policy

- **PROJECT.md (v2.0):** не упоминает license.
- **SKELETON.md §8 (deny.toml):** allows `"MIT"`, `"Apache-2.0"`, etc. GPL implicit denied.
- **CHARTER-0.1.md §4:** «Любые GPL-only библиотеки (у нас MIT/Apache-2.0 licensing)».

CHARTER-0.1 и SKELETON согласованы. PROJECT.md не упоминает licensing вообще.

**Правка:** D10 в PROJECT.md §3 (см. §2.5 выше) устраняет противоречие, добавляя explicit policy.

Это пример того, как fact-checking вылавливает внутренние gaps. Хорошо, что вылавливается рано.

---

## 5. Summary таблица правок

| Документ | Раздел | Тип правки | Размер |
|---|---|---|---|
| CHARTER-0.1.md | §10 | Clarification | +2 строки |
| CHARTER-0.1.md | §8 | Addition (Migration awareness) | +15 строк |
| SKELETON.md | §2 | Clarification | +1 строка |
| RUNTIME.md | §10 | Addition (Compositor-specific observations) | +20 строк |
| PLATFORM.md | §5 | Addition (Compositor-specific palette) | +12 строк |
| PROJECT.md | §3 | New decision D10 | +12 строк |
| RECON.md | §9 | License note | +3 строки |

**Total:** ~65 строк добавлений. Ноль строк удалений. Ноль изменений scope 0.1.

---

## 6. Что **не** входит в этот diff

Темы, которые всплыли в critique, но оставлены без правок сейчас:

- Полный redesign diagnostic codes с migration awareness — требует отдельного документа DIAGNOSTIC-CODES.md (уже в планах).
- `wpe-ipc-types` как public crate — решение для 1.0, не сейчас.
- Cooperation или inspiration с wpaperd author — это человеческое действие, не документная правка.

Эти темы — в `BACKLOG.md` (создаётся отдельно).

---

## 7. Процесс применения

1. Review этого DIFF как PR.
2. Обсуждение конкретных формулировок (особенно §2.3 и §2.4 — они новые).
3. Применение как batch commit: все правки одновременно, один changelog entry.
4. После применения — DIFF-v2.1.md архивируется (переименовывается в `archive/DIFF-v2.1-applied.md`).

---

## 8. Changelog

- **v2.1 draft (current)** — first batch of fact-based clarifications после external critique и fact-checking через web search. Все факты проверены и задокументированы.
