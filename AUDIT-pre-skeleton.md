# AUDIT — Deep Review pre-Skeleton

Статус: **audit only**. Не DIFF, не изменение документов. Фиксирует **что проверено**, **что найдено** и **что НЕ сделано намеренно**.

Проведён после v2.3 sync. Цель — поймать fact-based gaps, не добавить идей. Перед началом кода.

---

## Принцип audit

После восьми итераций документов соблазн найти «ещё одну сильную идею» стал опаснее, чем пропустить мелкий gap. Поэтому audit ищет **только** два класса проблем:

1. **Fact-based расхождения** — документы говорят X, а реальность API говорит Y.
2. **MSRV/версионные gaps** — документы не фиксируют constraint, который определит CI на первый же день.

Всё остальное — out of audit. «Может быть полезно добавить» игнорируется.

---

## 1. Что проверено

**Wayland client stack (Rust):**
- `smithay-client-toolkit` 0.19.2 — current stable. wgpu integration example — в client-toolkit/examples/, исторически ломался при bumps raw-window-handle.
- `wayland-client`, `wayland-protocols` — stable.
- `wp-fractional-scale-v1` — stable в wayland-protocols, поддержан wlroots, Sway, Hyprland.

**Render stack:**
- `wgpu` v29.0.1 — current stable. MSRV 1.87.
- `raw-window-handle` 0.6 — current.
- `CurrentSurfaceTexture` enum расширен: `Success / Timeout / Occluded / Outdated / Suboptimal / Lost / Validation`.

**Video stack:**
- `ffmpeg-next` 7.x — **maintenance-only mode** (автор не гарантирует review PR'ов).
- `rsmpeg` — активная альтернатива, FFmpeg 6/7, MSRV 1.81.
- `ez-ffmpeg` — высокоуровневый wrapper, но pulls больше зависимостей.

**Compositor reality:**
- hyprpaper v0.8.0 (oct 2025) — complete rewrite, configs сломаны.
- `swww` архивирован → `awww`.
- Hyprland fractional-scale: шлёт 1x initial, потом corrects. Image может быть blurry первые frames.
- niri: `place-within-backdrop` layer-rule, separate background per workspace.

---

## 2. Fact-based расхождения (5 найдено)

Каждое — точечное. НЕ применяется как DIFF, но должно быть **прочитано до первого commit** skeleton.

### F1. `PresentError` в RUNTIME.md не совпадает с wgpu v29 API

**RUNTIME.md §8** содержит:
```rust
pub enum PresentError {
    SurfaceLost,      // recreate Surface
    DeviceLost,       // recreate OutputRuntime
    Transient,        // retry next frame
}
```

**wgpu v29** использует `CurrentSurfaceTexture` enum с **семью** вариантами:
- `Success(frame)` — ok.
- `Timeout` — skip.
- `Occluded` — skip (surface скрыта, не нужно рендерить).
- `Outdated` — reconfigure surface.
- `Suboptimal(frame)` — frame есть, но нужен reconfigure после present.
- `Lost` — reconfigure surface, или recreate device если device lost.
- `Validation` — valid error только если зарегистрирован error handler.

**Impact:** наш `PresentError` теряет `Occluded` и `Suboptimal` — два важных случая. `Occluded` особенно — wallpaper daemon должен уметь пропускать frame когда ничего не видно, это оптимизация.

**Действие перед кодом:** обновить RUNTIME.md §8 в момент реализации `wpe-render-core::present`. **Не сейчас** — сейчас это preemptive change, который мы сами запретили. Когда дойдёт до реализации Renderer — посмотреть актуальный wgpu API и привести `PresentError` в соответствие.

**Это пример типа расхождения «документ опережает код».** Оно правильно решается не документной правкой, а ссылкой на актуальный wgpu API во время implementation.

### F2. MSRV не зафиксирован в документах

Ни в одном документе не указан MSRV (minimum supported Rust version). wgpu v29 требует 1.87. rsmpeg требует 1.81. ffmpeg-next исторически 1.65.

**Impact:** Первый `cargo build` на машине разработчика может fail на неожиданной причине. CI без explicit MSRV — ловушка.

**Действие перед кодом:** добавить в `Cargo.toml` workspace:
```toml
[workspace.package]
rust-version = "1.87"
```
И документировать в README после skeleton. **Не надо** добавлять это в CHARTER/PROJECT/PLATFORM — это build concern, не architectural.

### F3. `ffmpeg-next` в maintenance-only mode — риск для video stretch

**PROJECT.md §6 Corpus / CHARTER §2** упоминают ffmpeg для video backend. Но ffmpeg-next **не принимает большие PR'ы**, автор в maintenance-only mode.

**Impact на video stretch goal:**
- Если мы упираемся в API gap или bug — fix upstream может никогда не случиться.
- Альтернатива — `rsmpeg`. Активно поддерживается, больше features, но MSRV выше и API отличается.

**Действие:** НЕ менять документы сейчас. Когда будем реально писать `wpe-backend-video` (Milestone 6 stretch), **первым шагом** — сравнить ffmpeg-next vs rsmpeg на 3 тестовых файлах. Выбрать один. Зафиксировать выбор в `wpe-backend-video/README.md`. Это решение принадлежит implementation time, не charter'у.

**Связь с §13 CHARTER cutoff:** если ни одна из библиотек не даёт pass по трём checkpoint'ам к 2026-06-01 — video автоматически в 0.2. Это уже записано.

### F4. Hyprland fractional-scale initial 1x — поведение не описано в RUNTIME.md

**RUNTIME.md §10** говорит: «FractionalScale / Желательный в 0.1. Нет — integer scaling fallback + [W023]».

**Реальность Hyprland:** preferred_scale event сначала приходит как `120` (1.0), потом меняется на реальный (`150` для 1.25, `210` для 1.75). Между этими событиями у нас surface с неправильным scale.

**Impact:** первый кадр image будет blurry на Hyprland до receipt of correct scale. Это visible bug для пользователя.

**Действие перед кодом:** в `wpe-wayland/src/output.rs` в handler для `fractional_scale::preferred_scale`:
1. Defer первый present до receipt of scale event OR 100ms timeout.
2. При scale change после first present — trigger re-allocate texture с новым scale.

**Это implementation detail, не contract.** Записывать в RUNTIME.md — преждевременное документирование. Правильное место — комментарий в коде когда дойдём до output handling.

### F5. wp-fractional-scale требует wp_viewport — pair не зафиксирован

**RUNTIME.md §10** перечисляет `wp-fractional-scale-v1` как protocol, но не упоминает обязательное pair с `wp_viewport`.

Как работает correct fractional scaling:
1. Client получает `preferred_scale` через fractional_scale.
2. Client рендерит buffer в **native resolution** (scale * logical_size).
3. Client устанавливает через `wp_viewport::set_destination` — logical size.
4. Compositor scales и композит.

Без `wp_viewport` fractional не работает, будет fallback на integer scaling.

**Действие перед кодом:** когда будем реализовывать Wayland integration, **обязательно** bind `wp_viewporter` одновременно с `wp_fractional_scale_manager_v1`. В `wpe-wayland/src/lib.rs` их init — parallel, не separate paths.

**Опять — implementation detail.** Не редактируем RUNTIME.md превентивно.

---

## 3. Что НЕ сделано намеренно

Явный список вещей, которые я **заметил**, но **не добавил** в документы:

### N1. Не добавляю benchmark framework

Соблазн — зарегистрировать `criterion` для measure того, что CHARTER обещает (CPU < 25% @ 1080p/30fps video). **Отвергнуто:** benchmark framework — это целый подпроект. В 0.1 performance проверяется `heaptrack` + ручные измерения через `top`. Добавление criterion — 0.2 или позже.

### N2. Не добавляю tracing infrastructure детально

Соблазн — зарегистрировать `tracing` crate с правилами spans и полей. **Отвергнуто:** tracing добавляется по мере реальной потребности debug'а. Превентивно decorate каждую функцию `#[instrument]` — типичная ошибка Rust-проектов.

### N3. Не документирую compositor-specific workarounds

Соблазн — добавить `docs/known-issues.md` с записями типа «Hyprland scale issue», «niri place-within-backdrop», «labwc X». **Отвергнуто:** этот файл пишется **после** реальных столкновений с проблемами, не предугадывается. Превентивный docs/known-issues — мёртвый текст.

### N4. Не переношу `ffmpeg-next vs rsmpeg` в PROJECT.md как D11 decision

Соблазн — зафиксировать выбор сейчас. **Отвергнуто:** выбор зависит от реального поведения на 3 тестовых файлах. Принимается во время implementation Milestone 6, не сейчас.

### N5. Не добавляю MSRV как charter decision

Соблазн — добавить «D11. MSRV = 1.87» в PROJECT.md §3. **Отвергнуто:** MSRV — build concern, не architectural. Он живёт в `Cargo.toml` rust-version и в README. Documenting его как D-level decision — overengineering.

### N6. Не меняю wgpu `PresentError` в RUNTIME сейчас

Соблазн — привести enum в соответствие с v29 API превентивно. **Отвергнуто:** mapping между wgpu `CurrentSurfaceTexture` и нашим `PresentError` делается при реализации Renderer. Преждевременно — может устареть к моменту использования (wgpu v30 может выйти).

---

## 4. Что проверено и найдено OK

### OK1. Layer-shell API stability

`smithay-client-toolkit::shell::wlr_layer` stable. Wayland-protocols для layer-shell не имеет breaking changes последние 2 года.

### OK2. Rust ecosystem compatibility

MSRV 1.87 (wgpu requirement) — comfortable. Tokio 1.x stable. serde stable. iced не нужен в 0.1 (GUI вне scope). Все наши планируемые dependencies работают на одной MSRV.

### OK3. wlroots компиляторы покрывают наш целевой набор

Sway, Hyprland, niri, labwc, river, Wayfire — все реализуют zwlr-layer-shell-v1. Единственный compositor, у которого fractional-scale имеет known issue — Hyprland, и это фиксится handler'ом (F4).

### OK4. License compatibility

Наши планируемые dependencies: wayland-client (MIT), smithay-client-toolkit (MIT), wgpu (MIT/Apache), image (MIT/Apache), serde (MIT/Apache), tokio (MIT). ffmpeg-next / rsmpeg — LGPL-compatible wrapper, сам FFmpeg runtime — dynamic link, не заражает нашу MIT/Apache.

### OK5. SKELETON 4 crates — правильная граница

После проверки: 4 crate workspace (`wpe-compat`, `wpe-backend`, `wpe-render-core`, `wpe-contract-tests`) достаточно для всех 5 contract-tests из §6. Никаких hidden dependencies, которые заставят добавить 5-й crate.

---

## 5. Финальный вердикт audit

**Документы готовы для skeleton implementation.** Пять найденных расхождений (F1-F5) — все implementation-time, не charter-time. Они решаются в коде комментариями, в `Cargo.toml` (MSRV), или когда дойдёт до соответствующего Milestone.

Ни одно из расхождений **не** требует:
- Нового DIFF-цикла.
- Изменения scope 0.1.
- Обновления CHARTER/PROJECT/PLATFORM.

Изменения, которые будут происходить в реальных документах во время implementation:
- `RUNTIME.md §8 PresentError` — sync с wgpu v29 API при реализации Renderer.
- `RUNTIME.md §10` — добавление `wp_viewporter` как обязательной pair для fractional-scale при реализации Wayland layer.
- `wpe-backend-video/README.md` — выбор между ffmpeg-next и rsmpeg с обоснованием.
- `Cargo.toml` — `rust-version = "1.87"`.
- README.md (после skeleton) — список dependencies, MSRV, build instructions.

---

## 6. Meta-observation

Audit нашёл fact-based проблемы, но ни одна не требует превентивной документной правки. Это **правильное состояние** перед кодом:
- Документы не идеальны, но расхождения известны.
- Fixes — implementation-time, по мере реализации соответствующих компонентов.
- Список расхождений зафиксирован (этот документ), не в голове.

Следующий commit — `cargo new --lib crates/wpe-compat`.

Если через месяц audit v2 выявит новые расхождения — это хорошо. Такой audit дешевле, чем реальный рефакторинг.

---

## 7. Changelog

- **v1.0 (current)** — первый audit перед skeleton. Пять fact-based расхождений найдено, все implementation-time. Шесть соблазнов зафиксированы как явно отвергнутые (N1-N6).
