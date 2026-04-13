# Document Diff v2.2 — Final Sharpening

Статус: **draft for review**. Четвёртый и последний DIFF перед применением batch изменений.

**Принцип:** закрыть 4 реальных gap'а из финального critique, без расширения scope. Применяется **вместо** DIFF-v2.1.md — этот документ его includes и уточняет.

---

## 1. Preamble — что закрываем

Финальный critique выявил 4 точечные проблемы. Все 4 — подтверждены при проверке:

1. **Двойная persona 0.1.** Одновременно присутствуют «wlroots power user со свалкой daemons» (в PROJECT/CHARTER) и «hyprpaper/swww refugee» (вводится в DIFF-v2.1 через migration awareness). Это разные UX-углы. Нужна одна главная persona.

2. **0.1 перегружен.** Image + video + shader + GUI + profiles + diagnostics + pause policy + multi-output + hotplug — широкий scope. Нужно явное правило, что режется первым при трении.

3. **Напряжение между wlroots-only и future portability (D7).** Формулировка «не привязан глубже чем нужно» приглашает преждевременные абстракции.

4. **Phase II описана слишком уверенно.** Adapter к `linux-wallpaperengine` звучит как обязательство, хотя T3 уже предусматривает пересмотр. Психологический вес неправильный.

Дополнительно из DIFF-v2.1 переносим: **D10 licensing policy**.

---

## 2. Fact-checks перед правками

### 2.1. Соседи не имеют встроенного GUI

Подтверждено: `swaybg`, `swww`/`awww`, `hyprpaper`, `wpaperd`, `mpvpaper` — **ни один** не имеет встроенного GUI. GUI существует как отдельные проекты: `waypaper` (Python), `hyprwall` (Rust, GTK), `awtwall` (TUI), `waytrogen` (Rust, GTK4).

Hypr wiki явно перечисляет их как separate utilities. Это устоявшийся pattern экосистемы: **daemon отдельно, GUI отдельно**.

**Следствие для нас:** вынесение GUI из 0.1 в отдельный проект / отдельный релиз — не эксцентричное решение, а mainstream pattern.

### 2.2. Power user мигрирует между daemon'ами

Подтверждено: у пользователей regularly встречается pattern «свалка из swaybg + mpvpaper + scripts». Это **один и тот же пользователь**, который migrates из hyprpaper после 0.8 breakage. Две persona, которые я искусственно разделил, — **один человек в двух состояниях**.

**Следствие:** это не конкурирующие persona, это один main + одно состояние. Правильная формулировка: «wlroots power user, часто мигрирующий между daemon'ами из-за fragility соседей».

---

## 3. Четыре правки

### Fix 1. Unified main persona для 0.1

**Цель:** убрать искусственное разделение «power user» vs «refugee». Это один человек.

**Правка в CHARTER-0.1.md §1 — переписать полностью:**

```markdown
## 1. Первый пользователь

Один pattern, один человек. Если в дискуссии о фиче невозможно сказать, *как она
помогает этому пользователю на этой неделе*, — фича не в 0.1.

**Main persona: wlroots power user с fragile wallpaper stack.**

- Использует wlroots-based compositor (labwc, Hyprland, Sway, Wayfire, river, niri).
- Имеет один-три монитора, смешанное разрешение (HiDPI + стандарт — частый случай).
- На практике его стек — комбинация из нескольких tools, подобранных под разные
  задачи: swaybg/wpaperd для статики, mpvpaper для видео, скрипты для rotation.
- Регулярно сталкивается с breakage: swww архивирован в 2025, hyprpaper получил
  breaking config changes в v0.8.0 (late 2025), конфиги приходится мигрировать.
- Ценит в этом порядке:
  1. Стабильность — обои не пропадают после обновлений.
  2. Объединение image + video + shader в одном daemon.
  3. Per-output назначение без danса с конфигами.
  4. Actionable diagnostics — почему что-то не работает.

**Чего у main persona нет:** Steam с Wallpaper Engine. Желания ставить webkit.
Нужды в audio-reactive. Нужды в Lua в 0.1. Толерантности к ещё одному breakage.

**Secondary persona (diagnostic only, не driver features):** пользователь,
приходящий конкретно из hyprpaper/swww. Для него — migration awareness в
diagnostic system (§8). Не отдельная фича, просто diagnostic coverage.

**Не целимся в 0.1:** desktop environment users (GNOME/KDE), casual users без
wlroots опыта, Wallpaper Engine refugees, QML/Web creators. Эти люди существуют,
но не наш first-ring user.
```

**Замена триумфа на наблюдение:** убрано «Migration awareness — one of the strongest pivots», заменено на сдержанное «diagnostic coverage».

### Fix 2. Cut rule — что режется первым при обрезке 0.1

**Цель:** если implementation 0.1 начинает трещать, у нас должен быть **заранее зафиксированный порядок отступления**, не ad-hoc решение в момент панические.

**Правка в CHARTER-0.1.md — добавить новый §13:**

```markdown
## 13. Cut order — что режется первым при обрезке

Если по ходу 0.1 любое из условий возникает:
- Release criteria из §6 не достигаются за разумное время.
- Maintainer capacity снижается.
- Обнаруживаются архитектурные проблемы, требующие redesign.

— применяется **заранее зафиксированный порядок обрезки**. Не ad-hoc решение.

### Cut order (first to last)

1. **GUI.** Выносится в отдельный проект (`wpe-gui`), релизится независимо
   после 0.1 или не релизится вовсе в Фазе I. Обоснование: в экосистеме
   daemon и GUI — традиционно раздельны (waypaper, hyprwall, awtwall).
   Пользователь может использовать любой existing GUI через наш IPC.

2. **Shader backend.** Из трёх native backends — самый сложный (GLSL compile,
   hot reload, uniform protocol). Выносится в 0.2 если image + video
   стабилизируются первыми. Shader backend — tier C в PROJECT.md, он
   не fundamental для «wallpaper daemon» identity.

3. **Video backend.** Следующий кандидат, если shader уже вынесен.
   Пользователь с image-only wallpaper daemon — всё ещё полезный продукт.
   Video перенесётся в 0.2 с HW accel.

### Что НЕ режется никогда в 0.1

- Daemon + IPC (это суть продукта).
- Wayland integration layer (fractional-scale, layer-shell).
- Multi-output с hotplug.
- Image backend.
- Profile system v0.
- Diagnostics system.
- Contract infrastructure.

Без любого пункта из этого списка — продукт **не wallpaper daemon**, а tech demo.

### Правило применения

Обрезка — collective decision между maintainer'ами, зафиксированный в PR с меткой
`charter-0.1-cut`. Одного сигнала усталости — недостаточно. Два из трёх условий
выше — разрешают обрезку.
```

**Важно:** это не ослабляет 0.1 как обещание. Это даёт **safety valve**, который снижает риск полного провала.

### Fix 3. D7 — future portability с ограничением

**Цель:** убрать приглашение к преждевременным абстракциям, сохранив мысль.

**Правка в PROJECT.md §3 — переписать D7:**

**Было:**
```
### D7. wlroots-only, но Core не привязан к wlroots глубже, чем нужно

Platform Core абстрагирует Wayland integration так, чтобы в будущем не-wlroots
путь был **возможен** (не запланирован). Конкретно: layer-shell используется,
но не протекает через все слои.
```

**Становится:**
```
### D7. wlroots-only, без преждевременных абстракций

Platform Core пишется под wlroots с layer-shell. Non-wlroots support — out of
scope permanently (PROJECT.md §2).

Единственное ограничение на архитектуру: **не допускать решений, которые делают
future portability невозможной ценой нулевой текущей выгоды.**

Это означает:
- layer-shell types не просачиваются в `wpe-profile`, `wpe-ipc`, `wpe-compat`.
- Wayland-specific концепты живут в `wpe-wayland` crate.
- Если появляется искушение ввести `WaylandProtocolAbstraction` trait — **не вводить**.
  Прямой код под wlroots проще и честнее.

**Явно: никаких абстракций "на случай GNOME / KDE / Cosmic".** Если через три
года возникнет реальная потребность в non-wlroots backend — это будет отдельный
charter-change с конкретным use case и scope. Сейчас — прямой код под wlroots.
```

**Ключевое изменение:** «делаем задел» → «не пишем ненужных абстракций». Это противоположный вектор. Правильный.

### Fix 4. Phase II — target, не promise

**Цель:** психологически снизить вес adapter к `linux-wallpaperengine`. Это цель, не обязательство.

**Правка в PROJECT.md §1 — переписать блок про Фазу II:**

**Было:**
```
### Фаза II — Platform with Adapter Layer (1.x → 2.0)

Расширение 1.0 через adapter SDK. **Главная новая фича Фазы II** — adapter к
`linux-wallpaperengine`, дающий WE compat без собственного scene runtime.

Собственный WE runtime **не планируется никогда**. Если пользователю нужны
WE-обои — через adapter. Если adapter не справляется с конкретным типом обоев —
это ограничение upstream, не наша задача.
```

**Становится:**
```
### Фаза II — Platform with Adapter Layer (1.x → 2.0)

Расширение 1.0 через adapter SDK. **Основное направление Фазы II** — adapter к
`linux-wallpaperengine`, дающий WE compat без собственного scene runtime.

Это **цель, не обязательство**. Конкретно:
- Если upstream `linux-wallpaperengine` здоров к моменту старта Фазы II — делаем
  adapter как главную фичу 2.0.
- Если upstream stagnant / broken / заброшен (см. триггер T3) — Фаза II
  переопределяется. Возможные альтернативы: SDK для third-party backends как
  главная фича, profile activations system, или Фаза II не начинается вообще
  и проект остаётся на 1.x indefinitely.
- Собственный WE runtime **не планируется никогда**, независимо от состояния
  upstream.

Проект **не обязан** реализовать adapter любой ценой. Если 1.x оказывается
достаточным продуктом — Фаза II может не случиться, и это ОК.

**Scope Фазы II будет зафиксирован в CHARTER-2.0 в момент open'а Фазы II**, не
сейчас. Сейчас — только направление.
```

**Ключевое изменение:** «главная новая фича» → «основное направление». «Не планируется» → «не планируется никогда, независимо». «Фаза II случится» → «Фаза II может не случиться, это ОК».

---

## 4. Карры D10 (licensing) из DIFF-v2.1

Без изменений, остаётся как было:

**Правка в PROJECT.md §3 — добавить D10:**

```markdown
### D10. Licensing policy

Наш код — dual-licensed MIT / Apache-2.0. Это исключает ряд source-code references:

- `wpaperd` (GPL-3.0+) — изучаем как patterns reference, не копируем код.
- `linux-wallpaperengine` (GPL-3.0) — то же. Adapter в Фазе II общается через
  IPC/subprocess boundary, не linking.
- `mpvpaper` (GPL-3.0) — то же.
- `hyprpaper` (BSD-3-Clause) — compatible, но зависимостью не делаем по другим
  причинам (coupling с Hyprland).

Это не делает соседние проекты «хуже» — это техническое ограничение distribution
flexibility. Наш подход (MIT/Apache) позволяет включение в проекты с любой
совместимой лицензией.

Зависимости: только crates с compatible licenses (см. `deny.toml`).
```

---

## 5. Compositor-specific observations (из DIFF-v2.1, без изменений)

Без изменений. Добавление в RUNTIME.md §10 про niri / Treeland как observations,
не code paths.

---

## 6. Migration awareness (downgrade из DIFF-v2.1)

**Изменение тона:** в DIFF-v2.1 это было добавление к §8 CHARTER-0.1 как самостоятельная фича. Финальный critique справедливо указал, что это переносит акцент на secondary persona.

**Новая формулировка в CHARTER-0.1.md §8 — downgrade:**

```markdown
### Migration awareness (diagnostic coverage, не first-class feature)

Diagnostic system обнаруживает и признаёт common migration scenarios. Это **не
migration tool** и **не import feature**. Это просто diagnostic, которое
понимает, откуда пользователь приходит.

Пример:

```
[W050] hyprpaper config detected
  Location: ~/.config/hypr/hyprpaper.conf
  Info:     We are not hyprpaper-compatible. Our config format differs.
  Suggestion: See docs/migration/from-hyprpaper.md for equivalent configuration.
```

Это diagnostic. Не automated migration, не import format converter, не compat
layer.
```

Убрано «first-class feature», убрано упоминание «refugee». Это просто один из
warnings среди многих.

---

## 7. Summary финальных правок

| Документ | Раздел | Правка | Размер |
|---|---|---|---|
| CHARTER-0.1.md | §1 | Rewrite persona — unified main | ~25 строк заменены |
| CHARTER-0.1.md | §8 | Downgrade migration awareness | ~5 строк изменены |
| CHARTER-0.1.md | §13 (new) | Cut order — что режется первым | +30 строк |
| PROJECT.md | §1 | Rewrite Phase II — target не promise | ~15 строк заменены |
| PROJECT.md | §3 | Rewrite D7 — no premature abstractions | ~10 строк заменены |
| PROJECT.md | §3 | New D10 — licensing policy | +12 строк |
| RUNTIME.md | §10 | Compositor-specific observations | +20 строк (из v2.1) |
| PLATFORM.md | §5 | Compositor-specific palette note | +12 строк (из v2.1) |
| RECON.md | §9 | License note | +3 строки (из v2.1) |
| SKELETON.md | §2 | `wpe-ipc-types` reservation | +1 строка (из v2.1) |

**Total:** ~55 строк замен + ~80 строк добавлений = ~135 строк чистых изменений
в 6 файлах. Ноль расширений scope 0.1.

---

## 8. Что **всё ещё** не добавляю, несмотря на обсуждение

Для явности:

- **CompositorProfile.** Не в 0.1. Observations в RUNTIME.md — максимум.
- **Treeland protocol integration.** Не в 0.3. Filesystem + DBus.
- **Migration tools.** Не в 0.1. Только diagnostic awareness.
- **Adapter layer в 0.1.** Фаза II only.
- **GUI как ядро 0.1.** Первый кандидат на вынос при обрезке.
- **Self-promotion как «stability-first alternative».** До 6 месяцев после 1.0 — нет.
- **Wallpaper cycling в 0.1.** Не в 0.1. Возможно в 0.4 через activations.

---

## 9. Post-apply checklist

После применения этого DIFF:

- [ ] CHARTER-0.1 §1 показывает unified main persona.
- [ ] CHARTER-0.1 §13 описывает cut order (GUI → shader → video).
- [ ] PROJECT.md §1 Фаза II формулируется как «направление, не обязательство».
- [ ] PROJECT.md D7 запрещает premature abstractions.
- [ ] PROJECT.md D10 фиксирует licensing.
- [ ] DIFF-v2.1.md помечается superseded by DIFF-v2.2.md.
- [ ] Применяется как single batch commit с changelog entry
      `docs-v2.2: final sharpening before skeleton implementation`.

---

## 10. Что дальше

После применения DIFF — документы стабильны для начала skeleton implementation
(SKELETON.md §11).

Следующий ход не документный, а кодный:
1. Создание Cargo workspace.
2. Реализация `wpe-compat` с типами из SKELETON §3.
3. 12 contract-tests из SKELETON §6.

Документы подождут, пока не возникнут реальные расхождения между types и
контрактами. После skeleton — `FALLBACK-POLICY.md` и `DIAGNOSTIC-CODES.md`
получат конкретную почву.

---

## 11. Meta-observation

Этот DIFF — четвёртая итерация документов в рамках одного диалога. Каждая
итерация сужала scope и добавляла дисциплины. Это не anti-pattern, это как раз
здоровое развитие проекта через critique **до** написания кода.

Если после применения DIFF-v2.2 возникает 5-я итерация с новыми правками —
это сигнал остановиться. Все решения должны быть приняты, все противоречия
устранены, пора писать skeleton.

---

## 12. Changelog

- **v2.2 draft (current)** — четыре точечные правки после financial critique:
  unified persona, cut order, D7 anti-abstraction, Phase II как direction.
  Supersedes DIFF-v2.1.md (его изменения включены).
