# wpe-rs — Project Charter

Статус: **v2.0 stable**. Корневой документ проекта.

**Важно:** [CHARTER-0.1.md](./CHARTER-0.1.md) — выше этого документа. Если конфликт — побеждает CHARTER-0.1 (для всего, что касается 0.1). Этот документ говорит о долгосрочной картине.

Связанные документы:
- [CHARTER-0.1.md](./CHARTER-0.1.md) — жёсткие рамки первого релиза.
- [RUNTIME.md](./RUNTIME.md) — контракты рантайма.
- [PLATFORM.md](./PLATFORM.md) — граница Platform Core vs всё остальное.
- [RECON.md](./RECON.md) — snapshot экосистемы April 2026.
- [SKELETON.md](./SKELETON.md) — план первого компилирующегося скелета.

Изменение charter — PR с меткой `charter-change` и approver'ом из `CODEOWNERS`.

---

## 1. Рамка проекта — две фазы, один gate

Проект строится в **двух фазах**. Между ними — явный gate, без которого переход невозможен.

### Фаза I — Native Wayland Wallpaper Engine (0.1 → 1.0)

**Самостоятельный продукт.** Image-first: image backend (must-have), video (stretch goal с date-based cutoff, см. CHARTER-0.1 §13), мультимонитор, профили, CLI, диагностика. Shader, GUI, layered composition, Lua, palette, audio-reactive — в последующих релизах 0.x (см. §5 roadmap).

Конкурирует с экосистемой `swww`/`mpvpaper`/`hyprpaper`/`swaybg` путём объединения их функциональности под единым daemon с:
- Disciplined contracts и честным degraded mode.
- First-class profile system.
- Actionable diagnostics.
- Первоклассной обработкой Wayland edge cases (fractional scale, content-type hints, hotplug).

**Не конкурирует** с `linux-wallpaperengine` и KDE WE plugin в этой фазе вообще. WE compat = ноль кода в Фазе I.

### Gate между фазами

Переход Фазы I → Фазы II **не автоматический**. Разрешён только когда выполнены все условия:

1. **Release 1.0 выпущен** и все критерии релиза 1.0 выполнены.
2. **IPC freeze** — никаких breaking changes в IPC после 1.0.
3. **Stable API для Native Backends** — внутренний trait зафиксирован, можно на него рассчитывать.
4. **6 месяцев без critical bugs** на corpus A (нативные обои).
5. **Проект в активном maintenance mode ≥6 месяцев.** Regular releases (минимум bug fixes), responsive issue tracker (median TTFR < 2 недели), проект открыт к contributions. Множественность maintainers приветствуется, но формально не требуется — для indie-проекта это cage, не защита.
6. **Time gate:** Фаза II не может начаться **раньше, чем через 12 месяцев** после 0.1.

Пункт 6 защищает от преждевременного прыжка. Пункты 1-5 защищают от прыжка в нестабильное.

### Фаза II — Platform with Adapter Layer (1.x → 2.0)

Расширение 1.0 через adapter SDK. **Основное направление Фазы II** — adapter к `linux-wallpaperengine`, дающий WE compat без собственного scene runtime. Это **target, не обязательство**: если upstream `linux-wallpaperengine` окажется в плохом состоянии к моменту старта Фазы II (см. триггер T3), направление пересматривается.

Собственный WE runtime **не планируется никогда**. Если пользователю нужны WE-обои — через adapter. Если adapter не справляется с конкретным типом обоев — это ограничение upstream, не наша задача.

Дополнительные фичи Фазы II:
- SDK для сторонних backend'ов (adapter API публичен, документирован, semver-stable).
- Adapter к `mpvpaper` как пример community-backend (опционально, если будет заинтересованность).
- Profile activations (time-based, app-based, battery-based).

**Scope Фазы II тоже строго ограничен.** Отдельный CHARTER-2.0 будет написан в момент open'а Фазы II. Сейчас — детали не нужны.

---

## 2. Что мы **не** обещаем

Вневременные non-goals. Независимо от фазы.

### Never in scope

- **Web wallpapers через webkit2gtk.** WebKit ≠ Chromium, web community expects Chromium. Out of scope permanently.
- **Собственный WE scene runtime.** Только adapter к `linux-wallpaperengine` в Фазе II.
- **Godot integration.** Embedding — годы работы, Godot headless offscreen имеет свои pitfalls.
- **Unity integration.** Та же причина.
- **Live2D native integration.** Проприетарный SDK, licensing risks, не packageable.
- **Steam Workshop UI** прямо в daemon. В GUI — опционально через file-picker на папку workshop.
- **Theming engine.** Мы hook point (палитра + hooks), не GTK/Qt/terminal integration.
- **DRM-protected WE content.** Работать не будет принципиально.
- **Non-wlroots composer support.** GNOME Mutter, KWin без layer-shell, Cosmic — вне scope.
- **ARM platforms.** Не тестируем, не гарантируем.
- **NVIDIA proprietary driver first-class support.** Best-effort, community.

### Temporarily out of scope (может вернуться через charter-change)

- Любая WE compatibility в Фазе I.
- SDK для сторонних backends в Фазе I.
- Audio-reactive до 0.6.
- Grid-based pause detection до 0.2.
- HW video decoding до 0.2.

---

## 3. Архитектурные решения

Приняты. Изменение — charter-change PR.

### D1. Язык — Rust

Весь production-код. `unsafe` — только в явно помеченных FFI-модулях с safety comments.

### D2. **Один** render backend в 0.x

`wpe-render-wgpu` — единственный. Никакого `wpe-render-gl` в Фазе I.

**Обоснование.** Предыдущие версии этого документа предлагали два stack'а (wgpu для native, GL для WE compat). Поскольку собственный WE runtime снят с повестки навсегда (§1), необходимости в GL stack нет. Adapter к `linux-wallpaperengine` имеет свой GL context в external process — нас это не касается.

Если в Фазе II окажется, что adapter layer требует низкоуровневого GL interop с внешним процессом — это обсуждается отдельно в CHARTER-2.0.

### D3. Graphics API выше `wpe-render-core` неизвестен

Типы `wgpu::*` запрещены в `wpe-backend-*`, `wpe-compat`. Forbidden-imports lint в CI.

### D4. Корпус идёт перед кодом

До написания backend'а — собрать corpus wallpapers для тестирования. Для 0.1 это `corpus-A` (native).

### D5. Stop-критерии, не сроки

Каждый релиз имеет functional/quality/performance gate. Сроки — ориентировочные, не обязательства.

### D6. Web — out of scope permanent

Без шансов на возврат без создания отдельного проекта.

### D7. wlroots-only, без преждевременных абстракций

Platform Core пишется под wlroots с layer-shell. Non-wlroots support — out of scope permanently (§2).

Единственное ограничение на архитектуру: **не допускать решений, которые делают future portability невозможной ценой нулевой текущей выгоды.**

Это означает:
- layer-shell types не просачиваются в `wpe-profile`, `wpe-ipc`, `wpe-compat`.
- Wayland-specific концепты живут в `wpe-wayland` crate.
- Если появляется искушение ввести `WaylandProtocolAbstraction` trait — **не вводить**. Прямой код под wlroots проще и честнее.

**Явно: никаких абстракций "на случай GNOME / KDE / Cosmic".** Если через три года возникнет реальная потребность в non-wlroots backend — это будет отдельный charter-change с конкретным use case и scope. Сейчас — прямой код под wlroots.

### D8. Relationship к wlrs

`wlrs` (WERDXZ/wlrs) — ближайший проект на Rust. **Решение:** не fork, не collaborate активно, но **не конкурировать агрессивно**. Наш scope (platform + profiles + diagnostics + stability discipline) отличается от их scope (runtime + Lua + shader effects). Оба могут сосуществовать.

Если wlrs автор заинтересован в обмене идеями или extracting shared crates — welcome. Инициативы с нашей стороны — только через конкретный technical PR, не через «давайте объединимся».

### D9. Adapter layer = Фаза II, не Фаза I

Независимо от давления пользователей добавить `mpvpaper` adapter в 0.x — запрещено. Supervision external processes — отдельный подпроект, требующий своего фундамента.

---

## 4. Tier map

Уровни поддержки wallpaper types. Источник истины для числовых метрик — матрица в `wpe-compat`, не этот документ.

| Tier | Название | Когда | Примечания |
|---|---|---|---|
| A | Static image (PNG/JPG/WebP) | 0.1 | **Must-have Core** |
| B | Video (CPU path) | 0.1 stretch / 0.2 | Stretch с date-gate (CHARTER §13) |
| B+ | Video (HW accelerated, VA-API) | 0.2 | После B стабилен |
| C | GLSL fragment shader (Shadertoy-style) | **0.2** | Перенесён из 0.1 |
| C+ | WGSL shader | 0.4 | wgpu-native |
| D | Layered composition | 0.4 | Own format |
| E | Scripted (Lua) layers | 0.5 | Extends D |
| F | Audio-reactive | 0.6 | Requires D+E |
| G | Palette extraction + hooks | 0.3 | Theme integration |
| H | WE import (one-time conversion) | 1.x? | Only if technically clean |
| I | WE via `linux-wallpaperengine` adapter | 2.0 | Основное направление Фазы II |
| J | Third-party adapters | 2.x | Community |

Всё, что не в таблице, — out of scope до отдельного charter'а.

---

## 5. Roadmap — только до 1.0

Roadmap Фазы I. Фаза II имеет свой charter в свой момент.

Без сроков. Stop-gate'ы из [CHARTER-0.1.md §6](./CHARTER-0.1.md) для 0.1. Для остальных релизов — пишутся по мере приближения, но обязательная структура та же (functional / quality / performance).

### 0.1 — Image-First Native Core (Tier A + stretch B)

Описан подробно в CHARTER-0.1.md. Must-have: image. Stretch: video (см. §13 CHARTER). Shader, GUI, idle pause — **не в 0.1**.

### 0.2 — Shader + Video HW Accel + Smart Pause

- Shader backend (Tier C) — headline feature 0.2.
- Video (Tier B), если было вынесено из 0.1 stretch.
- Hardware video decoding (VA-API → DMA-BUF → wgpu external texture).
- Pause-on-idle через `ext-idle-notify-v1`.
- Grid-based pause detection (умная пауза).
- Damage tracking для статики.
- Battery-aware FPS cap через UPower.
- Минимум 60 дней после 0.1 stable.

### 0.3 — Palette & Theme Hooks

- Palette extraction из текущих обоев (dominant + accent).
- DBus signal `PaletteChanged`.
- User-defined post-hooks (`~/.config/wpe/hooks/on-palette-change.sh`).
- Документированные примеры интеграции с `wallust`, `matugen`.

### 0.4 — Layered Composition + Transitions

- Native формат `manifest.toml` с layers, z-index, opacity, blend modes.
- WGSL shader support.
- Transition effects между wallpapers.

### 0.5 — Lua Scripting

- Embedded `mlua` (Lua 5.4).
- Layer parameter animation через скрипты.
- Sandboxed API (no filesystem, no network).

### 0.6 — Audio-Reactive

- PipeWire capture через `pipewire-rs`.
- FFT через `rustfft`.
- Audio uniforms доступны в shader layers.

### 0.7-0.9 — Stabilization

Bug fixes, performance, ecosystem packaging (distro packages), документация, переводы. Никаких новых major features.

### 1.0 — Freeze

IPC stable. Backend API stable. CHANGELOG закрывается. Старт Фазы II gate.

---

## 6. Корпуса

Native corpus (`corpus-A`) — обязательный артефакт 0.1. Ступенчатый:

| Уровень | Размер | Состав |
|---|---|---|
| Seed | 10 | 6 image (разные форматы, размеры, EXIF edge cases), 4 video (разные codecs). Shader corpus — собирается перед 0.2. |
| Bootstrap | 30 | +5 каждого типа, разные разрешения, HDR, edge cases |
| Working | 50 | Для регрессионных тестов |

WE corpus в Фазе I **не собираем**. Он нужен только для Фазы II.

Детали структуры — в CORPUS.md (пишется параллельно с seed сбором).

---

## 7. Триггеры переоценки проекта

**T1.** Если на 0.1 Quality gate не достигается при трёх независимых попытках — пересмотреть scope 0.1 вниз (возможно релизить image-only без video, см. CHARTER §13).

**T2.** Если после 60 дней 0.1 stable появляется < 50 реальных пользователей — пересмотреть коммуникационную стратегию, не архитектурную.

**T3.** Если `linux-wallpaperengine` upstream умирает до Фазы II — пересмотреть adapter strategy (возможно, один из limited WE runtime modules в нас, со строгим scope, но это отдельный charter).

**T4.** Если Wayland layer-shell protocol значительно меняется (v5 с breaking changes) — адаптироваться, не паниковать.

---

## 8. Версионирование

- **0.1 → 1.0** — Фаза I. Semver не гарантируется между 0.x (breaking changes в IPC/config документируются в CHANGELOG).
- **1.0** — IPC freeze, config freeze.
- **1.x** — дополнения без breaking changes.
- **2.0** — Фаза II, adapter layer как основное направление (target, не обязательство).
- **2.x** — расширение SDK, больше community adapters.

Major version bump — charter-change.

---

## 9. Зачем этот документ в одной строке

**Мы строим узкое крепкое image-first wallpaper daemon для wlroots, с мультимонитором, профилями, честной диагностикой и disciplined contracts. Video — если успеем. Всё остальное — после 1.0.**

---

## 10. Changelog

- **v2.0 stable (current)** — переписано под двухфазную модель после трёх проходов по экосистеме и серии critical reviews. Отличия от v1.0:
  - Убран split на Продукты A/B/C.
  - Убран `wpe-render-gl` (один wgpu backend).
  - Убран собственный WE runtime навсегда.
  - Adapter layer зафиксирован как Фаза II only.
  - Добавлен time gate (12 мес) между фазами.
  - Добавлена ссылка на CHARTER-0.1 как высший документ для 0.1.
- **v1.0 draft** — первая версия. Архивирована.
