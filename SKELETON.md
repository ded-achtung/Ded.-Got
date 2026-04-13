# Skeleton Plan — First Compiling Scaffold

Статус: **v2.0 stable**. План первого компилирующегося каркаса.

Скелет переводит [RUNTIME.md](./RUNTIME.md) из текста в проверяемые типы. Не реализует функциональность. Цель — чтобы нарушение контракта ломало `cargo build` или `cargo test`, не review.

Связанные: [CHARTER-0.1.md](./CHARTER-0.1.md), [PROJECT.md](./PROJECT.md), [PLATFORM.md](./PLATFORM.md), [RUNTIME.md](./RUNTIME.md).

---

## 1. Цель skeleton

1. Реализовать ровно столько, чтобы RUNTIME.md перестал быть бумагой.
2. Нарушение контракта должно ломать `cargo build` или `cargo test`.
3. Выявить места, где документ плохо ложится в типы — и исправить **либо документ, либо код**.

Принцип: **если skeleton выявляет противоречие с RUNTIME.md — это успех, а не провал**.

---

## 2. Состав skeleton

Workspace содержит **только** следующие crate'ы:

```
wpe-rs/
├── Cargo.toml                  # workspace root
├── crates/
│   ├── wpe-compat/             # SupportMatrix, LoadReport, warnings
│   ├── wpe-backend/            # trait FrameSource + типы
│   ├── wpe-render-core/        # trait Renderer + handles
│   └── wpe-contract-tests/     # mock Renderer + contract tests
├── deny.toml
├── clippy.toml
├── tools/
│   └── forbidden-imports.sh
└── .github/workflows/ci.yml
```

Сознательно **не в skeleton**: `wpe-wayland`, `wpe-render-wgpu`, `wpe-backend-*`, `wpe-daemon`, `wpe-cli`, `wpe-gui`, `wpe-profile`, `wpe-ipc`. Они появляются после skeleton stable.

---

## 3. `wpe-compat`

```rust
// src/lib.rs
pub mod support;
pub mod report;
pub mod warning;
pub mod fallback;
```

### support.rs

Только то, что используется в 0.1. Video и shader добавятся как отдельные enum'ы в 0.2, когда появятся соответствующие backend'ы.

```rust
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum SupportLevel {
    Unsupported,
    Detected,
    Partial,
    Full,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum ImageFormat {
    Png,
    Jpeg,
    Webp,
    Unknown,
}

// TODO 0.2: pub enum VideoCodec { H264, H265, Vp9, Av1, Unknown }
// TODO 0.2: pub enum ShaderFeature { ShadertoyUniforms, TextureChannels, MouseInput, Unknown }

pub struct SupportMatrix {
    pub image_formats: std::collections::BTreeMap<ImageFormat, SupportLevel>,
    // TODO 0.2: video_codecs, shader_features
}

impl SupportMatrix {
    pub fn current() -> &'static SupportMatrix {
        static MATRIX: std::sync::OnceLock<SupportMatrix> = std::sync::OnceLock::new();
        MATRIX.get_or_init(default_matrix)
    }
}

fn default_matrix() -> SupportMatrix {
    use SupportLevel::*;
    SupportMatrix {
        image_formats: [
            (ImageFormat::Png, Full),
            (ImageFormat::Jpeg, Full),
            (ImageFormat::Webp, Full),
            (ImageFormat::Unknown, Unsupported),
        ].into_iter().collect(),
    }
}
```

Правило: тип заводится **когда появляется backend который его потребляет**, не превентивно. До имплементации video backend — `VideoCodec` нет в репозитории.

### report.rs

```rust
use crate::warning::CompatWarning;
use crate::fallback::IgnoredItem;

#[derive(Debug)]
pub struct LoadReport {
    pub status: LoadStatus,
    pub warnings: Vec<CompatWarning>,
    pub ignored: Vec<IgnoredItem>,
    pub asset_stats: AssetStats,
}

#[derive(Debug)]
pub enum LoadStatus {
    Ok,
    Partial { severity: PartialSeverity },
    Failed(LoadError),
}

#[derive(Debug, Clone, Copy)]
pub enum PartialSeverity { Cosmetic, Visible, Major }

#[derive(Debug)]
pub enum LoadError {
    ManifestInvalid(String),
    AssetMissing(std::path::PathBuf),
    FormatUnsupported { found: String, supported: Vec<String> },
    NegotiationFailed(String),
    Io(std::io::Error),
}

#[derive(Debug, Default)]
pub struct AssetStats {
    pub total_bytes: u64,
    pub image_count: u32,
    // shader_count — появляется в 0.2 вместе с shader backend.
    // video_frame_stats — появляются если video прошёл stretch gate в 0.1,
    // либо в 0.2 в противном случае.
}
```

### warning.rs

```rust
#[derive(Debug, Clone)]
pub struct CompatWarning {
    pub code: CompatWarningCode,
    pub context: String,
    pub suggestion: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CompatWarningCode {
    ImageSmallerThanOutput,           // W001
    ImageExifBroken,                   // W002
    VideoResolutionHuge,               // W010 (только если video в 0.1)
    FractionalScaleUnavailable,        // W023
    ViewporterUnavailable,             // W024 — wp_viewporter отсутствует,
                                       //        fractional scaling деградирует
                                       //        до integer scaling, хотя
                                       //        fractional-scale доступен.
    ContentTypeUnavailable,            // W025
    ForeignToplevelUnavailable,        // W040
    // W020 ShaderUndefinedUniform — в 0.2, вместе с shader backend.
    // W041 IdleNotifyUnavailable — в 0.2, вместе с pause-on-idle.
}
```

Полная таблица кодов — в `DIAGNOSTIC-CODES.md` (отдельный документ).

### fallback.rs

```rust
#[derive(Debug, Clone)]
pub struct IgnoredItem {
    pub category: &'static str,
    pub identifier: String,
    pub reason: &'static str,
}
```

В 0.1 `FallbackAction` минимален — большинство случаев решается через `LoadError::Failed` + fallback на solid color в Renderer. Расширенные fallback'и — в 0.4+.

---

## 4. `wpe-backend`

Зависит **только** от `wpe-compat`. Не зависит от `wpe-render-core` — trait `FrameSource` существует независимо.

```rust
// src/lib.rs
pub mod caps;
pub mod frame;
pub mod lifecycle;
pub mod state;
pub mod error;

pub use caps::*;
pub use frame::*;
pub use lifecycle::*;
pub use state::*;
pub use error::*;
```

### Ключевые определения

```rust
pub trait FrameSource: Send {
    fn capabilities(&self) -> BackendCapabilities;
    fn prepare(&mut self, ctx: PrepareCtx<'_>) -> wpe_compat::report::LoadReport;
    fn resize(&mut self, size: SurfaceSize, scale: FractionalScale)
        -> Result<(), BackendError>;
    fn update(&mut self, dt: FrameDelta, rt: &RuntimeState)
        -> Result<UpdateOutcome, BackendError>;
    fn produce(&mut self, req: &FrameRequest)
        -> Result<FrameOutput, BackendError>;
    fn pause(&mut self);
    fn resume(&mut self);
    fn status(&self) -> BackendStatus;
}

#[derive(Clone, Copy, Debug)]
pub enum FrameSourceKind {
    CpuRgba,
    DeviceEncoded,
    Static,
}

#[derive(Clone, Copy, Debug)]
pub enum PauseSemantics { Freeze, LogicOnly, Unsupported }

#[derive(Clone, Copy, Debug)]
pub enum ContentTypeHint { None, Photo }  // Video вернётся в 0.2

pub struct BackendCapabilities {
    pub source_kind: FrameSourceKind,
    pub resize: ResizePolicy,
    pub pause_semantics: PauseSemantics,
    pub content_type_hint: ContentTypeHint,
    // TODO 0.2: pub input: InputSupport         (нужен shader с mouse input)
    // TODO 0.2: pub damage: DamageSupport       (нужен при video для partial updates)
}
```

**Принцип:** для image backend все input/damage поля были бы `None`. Их отсутствие в 0.1 делает API honest — backend не врёт о capabilities, которых у него нет концептуально.

**Нет `DmaBuf` вариант FrameSourceKind** — добавится в 0.2 с HW accel.

### PrepareCtx и FrameRequest — через trait objects

```rust
pub struct PrepareCtx<'a> {
    pub allocator: &'a mut dyn ResourceAllocator,  // trait из render-core
    pub clock: RuntimeInstant,
}

pub struct FrameRequest<'a> {
    pub target_sink: &'a mut dyn TargetSink,  // trait из render-core
    pub target_size: SurfaceSize,
}
```

Trait'ы `ResourceAllocator` и `TargetSink` — в `wpe-render-core`. Backend знает их только через dyn — не импортирует `wgpu`.

---

## 5. `wpe-render-core`

Зависит только от `wpe-compat` и `wpe-backend`.

```rust
// src/lib.rs
pub mod renderer;
pub mod handles;
pub mod allocation;
pub mod target;
pub mod negotiation;
pub mod error;
```

### handles.rs

```rust
// Непрозрачные хэндлы. Внутренности — implementation detail Renderer.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct TextureHandle(pub(crate) u64);

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct BufferHandle(pub(crate) u64);

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct PipelineHandle(pub(crate) u64);

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct TargetHandle(pub(crate) u64);
```

### renderer.rs

```rust
pub trait Renderer {
    fn surface_format(&self) -> SurfaceFormat;
    fn surface_size(&self) -> SurfaceSize;

    fn negotiate(&self, caps: &BackendCapabilities) -> NegotiationResult;

    fn allocate(&mut self, req: &ResourceRequest)
        -> Result<ResourceHandles, AllocError>;

    fn present(&mut self, frame: FrameOutput)
        -> Result<PresentOutcome, PresentError>;

    fn status(&self) -> RendererStatus;
}
```

**Нет `DeviceKind`** — убран из Фазы I.

### allocation.rs

```rust
pub trait ResourceAllocator {
    fn allocate_texture(&mut self, desc: &TextureDesc)
        -> Result<TextureHandle, AllocError>;
    fn allocate_buffer(&mut self, desc: &BufferDesc)
        -> Result<BufferHandle, AllocError>;
    fn allocate_pipeline(&mut self, desc: &PipelineDesc)
        -> Result<PipelineHandle, AllocError>;
}
```

### target.rs

```rust
pub trait TargetSink {
    fn target_handle(&self) -> TargetHandle;
    // В 0.1 backend либо возвращает FrameOutput::Cpu, либо пишет
    // в target через отдельный API, который расширится в 0.4 (layered).
}
```

---

## 6. `wpe-contract-tests`

Тестовый crate. Содержит:
- `MockRenderer` — реализация `Renderer`, только учитывает вызовы.
- `MockAllocator`, `MockTargetSink`.
- `TracedBackend` — простой `FrameSource`, записывает порядок вызовов.
- Обязательные contract-tests.

### Пять contract-тестов (не двенадцать)

Каждый тест ловит конкретный класс багов, которые повторяются в wallpaper daemons. Имена читаемые — `cargo test lifecycle_order` без запоминания нумерации.

**`lifecycle_order`.**
Объединённый тест жизненного цикла. Проверяет три invariant'а:
- `prepare` вызывается до `update`/`produce`/`resize` — падение иначе.
- `resize` не вызывается во время `produce` — reentrancy guard в mock Renderer.
- `update` → `produce` парные; `produce` без предшествующего `update` — fail.

Ловит классический bug на hotplug: backend начинает получать события до того, как ему отдали ресурсы. Это один связный инвариант, нет смысла дробить его на три теста.

**`pause_idempotent`.**
Двойной `pause` — noop. Двойной `resume` — noop. `pause` после `pause` без `resume` не падает.

Ловит crash на burst событий от `ext-foreign-toplevel-list-v1`: композитор может прислать два fullscreen события подряд, backend должен это пережить.

**`present_recovery`.**
`PresentError::SurfaceLost` → Renderer делает recreate surface **ровно один раз**, продолжает работу. `PresentError::DeviceLost` → помечает себя fatal, OutputRuntime пересоздаётся.

Ловит разницу между «мигнул экран на 16ms» и «упал daemon». Без этого теста легко сделать одну общую ветку на обе ошибки и потерять recovery path.

**`no_gpu_in_backend`.**
Попытка `TracedBackend` импортировать `wgpu::Device` должна давать compile error. Реализуется через trait bounds + forbidden-imports.sh, сам тест — smoke проверка что guard на месте.

Дублирует forbidden-imports.sh частично, но оставляю: тест падает осмысленной ошибкой компиляции, а grep-скрипт — просто exit code 1. При отладке читаемость важна.

**`frame_output_invariants`.**
Проверяет что `FrameOutput::Cpu` содержит RGBA8 premultiplied, `Unchanged` никогда не возвращается при первом кадре, `SkippedDegraded` несёт non-empty reason. Это инварианты типа, а не жизненного цикла, но без них downstream-код (Renderer::present) делает wrong assumptions.

### Что сознательно НЕ тестируется отдельно

- **Negotiation чистота.** Это здравый смысл, не контракт рантайма. Комментарий в trait, не CI job.
- **SupportMatrix consistency.** Генерируется макросом из enum, тест не нужен.
- **Warning codes uniqueness.** Проверяется clippy lint или const assert, не runtime-тестом.
- **FrameSourceKind exhaustiveness.** Компилятор Rust уже это проверяет через exhaustive match без `_`.
- **Content-type propagation.** Преждевременно для 0.1 — там только статический `Photo`. Возвращается в 0.2 когда появится `Video` вариант.

Правило: тест добавляется только когда он ловит класс багов, который **реально случается** в подобных проектах. «Проверим на всякий случай» — нет.

### Пример `lifecycle_order`

```rust
#[test]
fn lifecycle_order() {
    let mut renderer = MockRenderer::new();
    let mut backend = TracedBackend::new();

    // update до prepare должен вызвать guard panic в MockRenderer.
    let rt = RuntimeState::mock();
    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        backend.update(FrameDelta::from_millis(16), &rt)
    }));
    assert!(result.is_err(), "update before prepare must fail");

    // После prepare — ок.
    let ctx = renderer.mock_prepare_ctx();
    let _ = backend.prepare(ctx);
    let ok = backend.update(FrameDelta::from_millis(16), &rt);
    assert!(ok.is_ok());

    // produce без предшествующего update — fail.
    let _ = backend.produce(&renderer.mock_frame_request());
    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        backend.produce(&renderer.mock_frame_request())
    }));
    assert!(result.is_err(), "two produce in a row without update must fail");

    // resize во время produce — fail через reentrancy guard.
    // (тест в mock Renderer, проверяет что produce устанавливает busy flag)
}
```

---

## 7. forbidden-imports lint

`tools/forbidden-imports.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

fail=0

check() {
  local dir="$1"
  local pattern="$2"
  local msg="$3"
  if grep -rE "$pattern" "$dir/src" >/dev/null 2>&1; then
    echo "FAIL: $msg"
    grep -rnE "$pattern" "$dir/src"
    fail=1
  fi
}

check "crates/wpe-backend"      '\buse\s+wgpu'   "wpe-backend must not import wgpu"
check "crates/wpe-render-core"  '\buse\s+wgpu'   "wpe-render-core must not import wgpu"
check "crates/wpe-compat"       '\buse\s+wgpu'   "wpe-compat must not import wgpu"

# В 0.1 нет wpe-render-gl, но правило зарезервировано.
# В Фазе II добавится check для wpe-backend на egl/gl.

exit $fail
```

---

## 8. cargo-deny policy

`deny.toml`:

```toml
[graph]
targets = [
    { triple = "x86_64-unknown-linux-gnu" },
]

[bans]
multiple-versions = "warn"

[licenses]
allow = [
    "MIT",
    "Apache-2.0",
    "Apache-2.0 WITH LLVM-exception",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "Unicode-DFS-2016",
    "Zlib",
]
# GPL не допускается — см. CHARTER-0.1 §4.
```

---

## 9. CI workflow

`.github/workflows/ci.yml`:

```yaml
name: ci

on:
  push: { branches: [main] }
  pull_request:

jobs:
  build-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - uses: Swatinem/rust-cache@v2
      - run: cargo build --workspace --all-targets
      - run: cargo test --workspace --all-targets

  clippy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
        with: { components: clippy }
      - run: cargo clippy --workspace --all-targets -- -D warnings

  forbidden-imports:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: bash tools/forbidden-imports.sh

  deny:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: EmbarkStudios/cargo-deny-action@v1
```

---

## 10. Stop-gate для skeleton

Skeleton готов (и проект может начинать реальный 0.1 code), когда:

**Functional:**
- [ ] `cargo build --workspace` успешен.
- [ ] `cargo test --workspace` зелёный, все 12 contract-tests.
- [ ] `forbidden-imports.sh` exit 0.
- [ ] `cargo clippy -- -D warnings` зелёный.
- [ ] `cargo deny check` зелёный.

**Quality:**
- [ ] 12 contract-tests реализованы. Отсутствующий — не merge.
- [ ] Каждый trait из RUNTIME.md §3 и §4 присутствует как Rust trait.
- [ ] Ноль `panic!`/`unwrap`/`expect` в production коде skeleton (кроме `unreachable!` с safety comment).

**Performance:** не оценивается.

**Дополнительно:**
- [ ] Любое расхождение между RUNTIME.md и типами задокументировано в `CONTRACTS-CHANGELOG.md` с пометкой «discovered during skeleton».
- [ ] Изменения документа — через PR `contract-change`, обновляющий RUNTIME.md и типы синхронно.

---

## 11. Порядок реализации skeleton

TDD для контрактов: тесты падают → трейты добавляются так, чтобы тесты зеленели. Альтернатива (сначала красиво описать трейты, потом написать тесты) приводит к красивым трейтам, которые тесты не покрывают.

Без дат, только порядок:

1. **Cargo workspace** с четырьмя пустыми crate'ами. CI с `cargo build` (пустые crate'ы компилируются).
2. **`wpe-compat`** — минимальные типы: `SupportLevel`, `ImageFormat`, `SupportMatrix` (только image), `LoadReport`, `LoadStatus`, `CompatWarningCode`. Без video, без shader.
3. **`wpe-contract-tests`** с пустыми `#[test]` функциями для пяти тестов из §6. **Тесты падают** — это ожидаемое состояние. Mock типы (`MockRenderer`, `TracedBackend`) — заглушки, которые достаточны чтобы тест компилировался но fail-ил.
4. **`wpe-backend::FrameSource` trait** — ровно столько методов, чтобы `lifecycle_order` компилировался. Дополнительные методы не добавляются превентивно.
5. **`wpe-render-core::Renderer` trait + handles** — столько, чтобы `present_recovery` компилировался.
6. Доимплементация `MockRenderer` и `TracedBackend` до состояния, когда **пять тестов зеленеют**.
7. **`forbidden-imports.sh`** + интеграция в CI. Тест `no_gpu_in_backend` проверяет, что скрипт действительно ловит `use wgpu` в backend.
8. **`deny.toml`** — licensing policy (MIT/Apache-2.0 only).
9. **Полный CI зелёный**: `cargo build --all`, `cargo test --all`, `cargo clippy -- -D warnings`, `forbidden-imports.sh`, `cargo deny check`.
10. Возникающие расхождения между типами и RUNTIME.md — PR к документу, не к коду.

Skeleton готов когда пункты 1-9 выполнены.

**Важно:** на шаге 4-5 будет желание добавить методы «чтобы было». Правило — добавляется только то, что нужно для одного из пяти тестов. Всё остальное — `// TODO 0.2` в коде, не в trait.

---

## 12. После skeleton

Порядок реализации. **`wpe diag` — первый real-code milestone**, не image backend.

### Почему diag first, не image

Image backend кажется простой отправной точкой («ну картинку-то точно нарисуем»). На практике он тянет за собой:
- EGL context на `wl_surface`.
- wgpu initialization.
- Texture upload pipeline.
- Surface resize handling.
- Fractional-scale edge cases на разных композиторах.

Если начать с image, первые две недели уйдут на отладку рендера, и у вас не будет инструмента, чтобы понять, **где конкретно** что-то сломалось на чужой машине.

`wpe diag` — пустой daemon, который умеет только одно: подключиться к Wayland и честно сказать «вот что я вижу». Это:
- Ранняя победа (через 2-3 дня после skeleton есть запускаемый бинарь).
- Инструмент для отладки всего остального (когда image не работает на Hyprland — `wpe diag` покажет почему).
- Валидация Wayland integration layer до того, как туда приложен рендер.
- Готовый фундамент для `wpectl status` из §8 CHARTER.

### Порядок

1. **`FALLBACK-POLICY.md`** — полная таблица fallback'ов на основе существующих типов.
2. **`DIAGNOSTIC-CODES.md`** — каталог warning codes (W001, W002, W010, W023, W024, W025, W040 для 0.1; W020, W041 резервируются под 0.2).
3. **Milestone 1: `wpe diag`.** Бинарь `wpe-daemon` + `wpectl diag`. Подключение к Wayland, enumerate protocols, проверка каждого optional protocol, вывод structured report. Никакого рендера. Никакого IPC для `set`. Никаких backend'ов.
   - **Success criterion:** `wpectl diag` на labwc/Hyprland/Sway/Wayfire/niri выдаёт корректный report. Каждый warning code соответствует реальному состоянию композитора.
4. **Milestone 2:** IPC skeleton (`set` command), config store (TOML), profile system v0 (в памяти, без persistence).
5. **Milestone 3:** `wpe-wayland` (layer-shell, output management, hotplug) + `wpe-render-wgpu` init. Всё ещё без backend'ов — surface создаётся, wgpu initialized, clear color.
6. **Milestone 4:** `wpe-backend-image`. Первый реальный wallpaper на экране.
7. **Milestone 5:** Multi-output hotplug, fractional-scale edge cases, profile persistence.
8. **Milestone 6 (stretch):** `wpe-backend-video` — если до 2026-06-01 (см. CHARTER §13).
9. **Release 0.1.**

### Что НЕ в этом списке

- GUI — out of Phase I scope (CHARTER §4).
- Shader backend — перенесён в 0.2.
- Pause-on-idle — в 0.2.
- Adapter layer — Phase II.

Любой пункт, который хочется добавить в этот список, — останавливаемся и проверяем по CHARTER §4 (запрещённые features). Если там — фича не добавляется.

За пределами этого документа — имплементация каждого milestone.

---

## 13. Changelog

- **v2.0 stable (current)** — обновлён под CHARTER-0.1 scope и убран dual render stack.
  Отличия от v1.0:
  - Удалены типы `DeviceKind`, `DeviceKind::{Wgpu, EglGl}`.
  - Удалены упоминания `wpe-render-gl`.
  - `FrameSourceKind::DmaBuf` удалён (возвращается в 0.2).
  - Удалён `DrawListSink` и связанные типы (layered composition — 0.4).
  - `SupportMatrix` упрощена под 0.1 scope (image/video/shader).
  - Добавлены CT-11 и CT-12 (PresentError recovery, content-type propagation).
  - Удалён раздел про `wpe-backend-scene`.
- **v1.0 draft** — архивирована.
