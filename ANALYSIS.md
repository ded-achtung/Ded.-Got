# Анализ проекта wpe-rs

Дата анализа: 2026-04-13

---

## 1. Общее описание

**wpe-rs** — проектируемый wallpaper daemon для wlroots-based Wayland-композиторов (Hyprland, Sway, labwc, river, niri, Wayfire), написанный на Rust. Цель — заменить пользователю разрозненный стек (`swaybg` + `mpvpaper` + скрипты) единым daemon с профилями, IPC, диагностикой и стабильными контрактами.

**Текущий статус:** фаза документирования и прототипирования. Код — один throwaway prototype (~390 строк), документация — ~4200 строк (~250 KB) в 12 markdown-файлах.

---

## 2. Структура репозитория

| Файл | Строк | Назначение |
|---|---|---|
| `CHARTER-0.1.md` | 267 | Жёсткая рамка релиза 0.1 — высший документ |
| `PROJECT.md` | 281 | Двухфазная модель, архитектурные решения D1-D10, roadmap до 1.0 |
| `PLATFORM.md` | 360 | Три слоя: Platform Core / Backend API / Extensions, правила B1-B5 |
| `RUNTIME.md` | 603 | Контракты рантайма (частично устарели, PROTOTYPE-PENDING) |
| `SKELETON.md` | 644 | Plan первого компилируемого скелета, 4 crate'а, 5 contract-tests |
| `SELF-AUDIT.md` | 269 | Honest audit — 8 gap'ов, 2 критичных |
| `AUDIT-pre-skeleton.md` | 219 | 5 implementation-time находок |
| `RECON.md` | 266 | Snapshot экосистемы wallpaper tools (April 2026) |
| `DIFF-v2.{1,2,3}.md` | 1092 | Архив итераций документов |
| `README.md` | 109 | Навигация по проекту |
| `main.rs` | 391 | Throwaway prototype — calloop + layer-shell + wgpu |
| `Cargo.toml` | 51 | Manifest прототипа (6 зависимостей) |

---

## 3. Архитектурные решения

Проект принял 10 ключевых решений (D1-D10):

| ID | Решение | Комментарий |
|---|---|---|
| D1 | Язык — Rust | `unsafe` только в FFI с safety comments |
| D2 | Один render backend (wgpu) | Никакого GL-stack в Phase I |
| D3 | Graphics API скрыт за `wpe-render-core` | `wgpu::*` запрещён в backend'ах, lint в CI |
| D4 | Корпус обоев перед кодом | corpus-A (native) для регрессий |
| D5 | Stop-критерии, не сроки | Functional + Quality + Performance gate |
| D6 | Web — out of scope permanent | WebKit/Chromium никогда |
| D7 | wlroots-only, без premature abstractions | Никаких абстракций «на случай GNOME/KDE» |
| D8 | Не fork wlrs, не конкурировать | Разные scope, мирное сосуществование |
| D9 | Adapter layer = только Phase II | Даже под давлением пользователей |
| D10 | MIT/Apache-2.0 лицензия | GPL не допускается |

---

## 4. Двухфазная модель

### Phase I (0.1 → 1.0) — Native Wayland Wallpaper Engine
- **0.1**: Image-first core (PNG/JPG/WebP) + video как stretch goal с date-gate (2026-06-01)
- **0.2**: Shader backend (GLSL), HW video (VA-API), smart pause, battery FPS cap
- **0.3**: Palette extraction + theme hooks
- **0.4**: Layered composition, WGSL shaders, transitions
- **0.5**: Lua scripting (mlua)
- **0.6**: Audio-reactive (PipeWire + FFT)
- **0.7-0.9**: Stabilization
- **1.0**: IPC freeze, backend API freeze

### Phase II (1.x → 2.0) — Platform with Adapter Layer
- Adapter SDK (pubличный API)
- Adapter к `linux-wallpaperengine`
- Time gate: 12 месяцев минимум между фазами

---

## 5. Состояние кода

### Prototype (`main.rs`, 391 строка)
Throwaway prototype проверяет 4 архитектурных Gap'а:

- **Gap 1** (calloop vs tokio): Выбран calloop-first, single-thread, no tokio — подтверждён прототипом
- **Gap 2** (frame callback): Единый `render_frame(is_first)` вместо `update`+`produce` pair
- **Gap 3** (layer-shell lifecycle): create → empty commit → wait configure → ack → attach buffer
- **Gap 4** (damage tracking): full damage на первый кадр, пустой для статики

Технологический стек прототипа:
- `wayland-client` 0.31 + `smithay-client-toolkit` 0.19
- `calloop` 0.14 + `calloop-wayland-source` 0.4
- `wgpu` 29 + `pollster` 0.4
- MSRV: Rust 1.87

**Прототип не скомпилирован и не запущен на реальной машине.** Содержит `unsafe` (`mem::transmute` для `Surface<'static>`), который заменится на `Arc<WlSurface>` в production.

---

## 6. Найденные проблемы и gap'ы

### Критичные (severity: HIGH)

| Gap | Проблема | Статус |
|---|---|---|
| Gap 1 | Async model: RUNTIME.md описывал tokio-first, реальность — calloop-first | Прототип написан, RUNTIME §9 помечен PROTOTYPE-PENDING |
| Gap 2 | Frame callback model отсутствовала, `update`+`produce` pair не совместим с Wayland | Прототип показал правильную модель, RUNTIME §3 помечен PROTOTYPE-PENDING |

### Средние (severity: MEDIUM)

| Gap | Проблема | Статус |
|---|---|---|
| Gap 3 | Layer surface lifecycle contract не описан | Описан в RUNTIME §2 как PROTOTYPE-PENDING |
| Gap 4 | Double-buffered state и damage tracking не учтены в Renderer contract | Частично закрыт прототипом |
| Gap 6 | Performance метрики в CHARTER §6 не верифицированы | Ждут запуска прототипа на реальном оборудовании |

### Foundational

| Gap | Проблема | Статус |
|---|---|---|
| Gap 5 | ~2300 строк документации при 0 строк production кода | Осознанно, prototype-first подход принят |

### Низкие (severity: LOW)

| Gap | Проблема | Статус |
|---|---|---|
| Gap 7 | `deny.toml` не полный (только licenses) | Skeleton-time |
| Gap 8 | Нет примера wgpu на Wayland в SKELETON | Закрывается прототипом |

---

## 7. Scope 0.1 — что входит, что нет

### Must-have (в 0.1)
- Image backend (PNG, JPG, WebP) с fit modes (cover, contain, stretch, tile, center)
- Multi-output через layer-shell
- Hotplug мониторов
- Fractional scale (wp-fractional-scale-v1 + wp_viewporter pair)
- Profile system (minimal: per-output assignment, manual switching)
- IPC (Unix socket, JSON): SetProfile, GetActiveProfile, ListProfiles, etc.
- CLI (`wpe` binary): profile set, output list, status, diag
- Pause on fullscreen (через ext-foreign-toplevel-list-v1)
- `wpe diag` — structured diagnostics

### Stretch (с date-gate 2026-06-01)
- Video backend (CPU path через ffmpeg, H.264/H.265/VP9/AV1)

### Явно НЕ в 0.1
- Shader backend → 0.2
- GUI → вне Phase I
- Pause-on-idle → 0.2
- Palette/theming → 0.3
- Layered composition → 0.4
- Lua scripting → 0.5
- WE compat → Phase II (2.0)
- Web wallpapers → никогда в Core

---

## 8. Планируемая architecture (skeleton)

```
wpe-rs/
├── crates/
│   ├── wpe-compat/           # SupportMatrix, LoadReport, warnings
│   ├── wpe-backend/          # trait FrameSource + типы
│   ├── wpe-render-core/      # trait Renderer + handles
│   └── wpe-contract-tests/   # mock'и + 5 contract-tests
├── deny.toml
├── clippy.toml
├── tools/forbidden-imports.sh
└── .github/workflows/ci.yml
```

Post-skeleton milestones:
1. `wpe diag` — первый real milestone (до image backend)
2. IPC skeleton + config store
3. `wpe-wayland` + `wpe-render-wgpu` init (clear color)
4. `wpe-backend-image` — первый реальный wallpaper
5. Multi-output, hotplug, fractional-scale
6. `wpe-backend-video` (stretch, до 2026-06-01)
7. Release 0.1

---

## 9. Качество документации

### Сильные стороны
- **Исключительная дисциплина scope.** Документы чётко разделяют must/stretch/out-of-scope с конкретными номерами релизов
- **Честный self-audit.** SELF-AUDIT.md признаёт foundational gaps без попытки их скрыть
- **Anti-scope-creep механизмы.** Date-based cutoff для video (§13), Q1-Q8 запреты в CHARTER, B1-B5 boundary rules в PLATFORM
- **Иерархия документов.** CHARTER-0.1 > PROJECT > RUNTIME > SKELETON — ясный порядок приоритетов
- **Actionable diagnostics.** Warning codes с context, impact и fix suggestion
- **Prototype-first корректировка.** Вместо бесконечных итераций документов — решение прототипировать

### Слабые стороны
- **Документы написаны до кода.** 250 KB документации при 0 строк production кода — инвертированный процесс
- **3 секции RUNTIME.md устарели** и помечены PROTOTYPE-PENDING
- **SKELETON §10 ссылается на 12 contract-tests**, но §6 описывает только 5 — inconsistency
- **Performance targets не верифицированы** (CPU <1% для статики, <25% для video) — цифры из головы
- **Нет запускаемого кода** — прототип не компилировался
- **Архивные DIFF-v2.x** занимают ~60 KB, но несут только историческую ценность

### Inconsistencies найденные при анализе
1. SKELETON §10 говорит "все 12 contract-tests", а §6 описывает 5 тестов
2. RUNTIME §3 описывает `FrameSource` с `update`+`produce`, но PROTOTYPE-PENDING говорит о едином `render_frame` — trait shape не обновлён
3. SKELETON §6 CompatWarning содержит `VideoResolutionHuge` (W010), но video может не войти в 0.1
4. SupportMatrix в RUNTIME §5 содержит `video_codecs` поле, а SKELETON §3 его комментирует как TODO — рассогласование

---

## 10. Рекомендации

### Критический путь (блокирует всё остальное)
1. **Скомпилировать и запустить прототип** на реальном wlroots-компизиторе
2. **Обновить RUNTIME §2, §3, §9** по результатам запуска (снять PROTOTYPE-PENDING)
3. **Измерить реальные метрики** (CPU, memory, startup time) и обновить CHARTER §6

### Следующие шаги
4. **Исправить inconsistency** SKELETON §10 (12 tests → 5 tests)
5. **Начать skeleton** — 4 crate workspace, CI pipeline
6. **`wpe diag` milestone** — первый запускаемый бинарь
7. **Собрать corpus-A** (seed: 10 файлов) параллельно с skeleton

### Что НЕ делать
- Ещё один проход по документам (DIFF v2.4)
- Переписывать RUNTIME без прототипа
- Добавлять фичи в scope 0.1
- Начинать image backend до `wpe diag`
