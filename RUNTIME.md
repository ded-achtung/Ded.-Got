# Runtime Contracts

Статус: **v2.0 draft + PROTOTYPE-PENDING sections**. Стабилизируется после запуска `prototype-main.rs` на wlroots компизиторе и обновления §2, §3, §9 по фактическим результатам.

Документ для репозитория. Только контракты, по которым работает рантайм.

Roadmap — в [PROJECT.md](./PROJECT.md). Scope 0.1 — в [CHARTER-0.1.md](./CHARTER-0.1.md). Границы Core — в [PLATFORM.md](./PLATFORM.md). Архитектурные gap'ы — в [SELF-AUDIT.md](./SELF-AUDIT.md).

Пересмотр — PR с меткой `contract-change` и approver'ом из `CODEOWNERS`. Нарушение контракта в коде — bug, не «особенность реализации».

---

## ⚠️ PROTOTYPE-PENDING sections

Следующие разделы **устарели** относительно SELF-AUDIT.md и `prototype-main.rs`.
Они **не должны** использоваться как руководство к написанию кода сейчас.
Будут переписаны после запуска прототипа на реальной машине.

| Раздел | Что устарело | Правильная модель (из прототипа) |
|---|---|---|
| §2 (иерархия) | Нет layer-shell lifecycle state machine | create → empty commit → WAIT configure → ack → attach |
| §3 (FrameSource) | `update` + `produce` pair | Единый `render_frame(is_first)`, вызываемый из callback |
| §9 (threading) | tokio-first, separate Wayland thread | calloop-first на main thread, no tokio в 0.1 |

Остальные разделы (§1, §4-8, §10-15) — **не затронуты** SELF-AUDIT'ом и остаются руководством к коду.

---

## 0. Глоссарий

- **Frame** — один законченный визуальный кадр, готовый к презентации в `wl_surface`.
- **FrameSource** — сущность, способная по запросу предоставить Frame. Не рисует в финальный surface сама.
- **Backend** — конкретная реализация `FrameSource`. В 0.1: **image** (must-have) и **video** (stretch, см. CHARTER-0.1 §13). **Shader** — в 0.2, не в 0.1.
- **Renderer** — берёт `FrameOutput` и презентует его в surface конкретного монитора.
- **Device** — владелец GPU-ресурсов (`wgpu::Device`).
- **OutputRuntime** — пара (Backend, Renderer) на один wl_output.
- **Surface** — `wl_surface` + `zwlr_layer_surface_v1` + wgpu surface.
- **Degraded** — состояние, когда Backend работает с ограничениями. **Не ошибка.**
- **Failed** — состояние, когда Backend не может продолжать. Ошибка.

Запрещены в коде без уточнения: `engine`, `manager`, `system`.

---

## 1. Принципы

Не подлежат обсуждению без contract-change PR.

**P1. Односторонний поток владения GPU-ресурсами.**
GPU-ресурсы аллоцируются только внутри Renderer. Backend **не имеет права** создавать текстуры, буферы, шейдеры, pipeline напрямую. Backend описывает, что нужно; Renderer выделяет.

**P2. Никакого знания про graphics API выше `wpe-render-core`.**
Типы `wgpu::*` запрещены в `wpe-backend-*`, `wpe-compat`. Forbidden-imports lint в CI.

**P3. Degraded — это тип, а не строка в логе.**
Любой возврат из `prepare`/`update`/`produce` несёт машиночитаемый статус. Warning без кода — запрещён.

**P4. Backend не знает, сколько у него мониторов.**
Один Backend = один OutputRuntime. Одни и те же обои на двух мониторах = два независимых backend.

**P5. Fallback — явное решение, не отсутствие реализации.**
Молчаливый skip запрещён.

**P6. Единица времени — `RuntimeInstant`.**
Не `std::time::Instant`, не wall clock. Монотонное время рантайма, ставится на паузу. Backend использует только его.

**P7. Один render stack.**
В Фазе I — только `wpe-render-wgpu`. `DeviceKind` enum не существует. Если в Фазе II понадобится второй stack — это отдельный contract change.

---

## 2. Иерархия владения

```
Daemon
 ├── WaylandConnection                    (один)
 ├── IpcServer                             (один)
 ├── ConfigStore                           (один)
 ├── ProfileManager                        (один)
 └── OutputRuntime[]                       (по одному на wl_output)
      ├── Surface                          (layer_surface + wgpu surface)
      ├── Renderer                         (владеет wgpu::Device)
      │    └── GpuResources                (textures, buffers, pipelines)
      └── Backend                          (единственный текущий)
           └── BackendAssets                (CPU-side: декодеры, state)
```

**Правила:**

- Backend создаётся **после** Renderer и уничтожается **раньше**.
- При замене обоев пересоздаётся только Backend. Renderer и Surface живут.
- При hotplug монитора OutputRuntime пересоздаётся целиком.
- Daemon никогда не держит прямых ссылок на GpuResources.

> ⚠️ **PROTOTYPE-PENDING — layer-shell lifecycle не описан в контрактах.**
>
> SELF-AUDIT.md Gap 3: создание OutputRuntime имеет **обязательную protocol-level
> sequence**, которую текущий документ не кодифицирует. Это bypass критического
> инварианта Wayland.
>
> **Правильная последовательность (spec wlr-layer-shell-v1):**
> 1. `compositor.create_surface()` → `wl_surface`.
> 2. `layer_shell.create_layer_surface(wl_surface, ...)` → `zwlr_layer_surface_v1`.
> 3. `set_anchor` / `set_size` / `set_keyboard_interactivity`.
> 4. **`wl_surface.commit()` — initial commit БЕЗ буфера.**
> 5. **WAIT** — compositor отправляет `configure(serial, width, height)`.
> 6. `ack_configure(serial)`.
> 7. **Теперь** можно создать wgpu surface и attach buffer.
> 8. Render первый кадр с full damage.
> 9. `wl_surface.commit()`.
>
> Попытка attach buffer до configure = protocol error, compositor kill-ит клиент.
>
> **Что это значит для OutputRuntime:**
> - Backend **не может** быть создан сразу с OutputRuntime — только после configure.
> - Renderer тоже создаётся после configure (wgpu surface требует valid size).
> - OutputRuntime имеет внутренний state machine: `PendingConfigure → Configured → Live`.
>
> **Когда переписывается:**
> Это видно в `prototype-main.rs` (флаг `configured`, вся логика init в
> `LayerShellHandler::configure`). После запуска прототипа — переносим эту
> model в §2 как явный lifecycle state machine + добавляем contract-test
> `layer_surface_lifecycle` (это будет 6-й тест, не 5-й как сейчас в SKELETON).

---

## 3. Контракт `FrameSource`

> ⚠️ **PROTOTYPE-PENDING — trait shape не проверен кодом.**
>
> SELF-AUDIT.md Gap 2 зафиксировал: этот trait имеет разделение `update` + `produce`
> как pair вызовов от Renderer к Backend. Но **Wayland не работает по этой модели**.
>
> Wayland render cycle driven **compositor'ом через `wl_callback::done`**:
> 1. Client вызывает `wl_surface::frame(callback)` → commit.
> 2. Compositor решает когда готов принять следующий кадр → отправляет `done(time)`.
> 3. Client рисует → attach buffer → damage → commit → запрашивает следующий callback.
>
> **Что это значит для FrameSource:**
> - Один entry point `render_frame(now)`, не два (`update` + `produce`).
> - Вызывается **из callback handler'а** (см. §9 calloop-first model).
> - `is_first_frame` флаг для damage tracking (см. Gap 4).
>
> **Что видно из `prototype-main.rs`:**
> - Handler `CompositorHandler::frame()` — hook для callback done.
> - Функция `render_frame(layer, is_first)` — единственная render entry point.
> - Для image backend (статика) callback не запрашивается на каждый кадр —
>   только после изменения (смена wallpaper). Для video/shader — на каждый.
>
> **Когда переписывается:**
> После запуска прототипа. Результат — единый метод `render_frame` вместо
> `update`+`produce`, с явным контрактом про damage и frame-callback driven
> invocation. Contract-tests также пересматриваются (вместо CT `update-produce
> pairing` будет CT `damage_on_first_frame` и `callback_requested_on_animated`).
>
> **Текущий текст ниже описывает trait который **не** будет implemented as-is.
> Оставлен для диффа.**

Единственный контракт между Renderer и Backend (устаревший draft).

```rust
pub trait FrameSource: Send {
    fn capabilities(&self) -> BackendCapabilities;

    fn prepare(&mut self, ctx: PrepareCtx<'_>) -> LoadReport;

    fn resize(&mut self, size: SurfaceSize, scale: FractionalScale)
        -> Result<(), BackendError>;

    // ⚠️ update + produce pair — PROTOTYPE-PENDING переработка в единый render_frame.
    fn update(&mut self, dt: FrameDelta, rt: &RuntimeState)
        -> Result<UpdateOutcome, BackendError>;

    fn produce(&mut self, req: &FrameRequest)
        -> Result<FrameOutput, BackendError>;

    fn pause(&mut self);
    fn resume(&mut self);

    fn status(&self) -> BackendStatus;
}
```

### Инварианты жизненного цикла

- `capabilities` — чистая, можно вызвать в любой момент.
- `prepare` — ровно один раз, до любого другого метода (кроме `capabilities`).
- `resize` — не во время `produce`. Только между кадрами.
- `update` предшествует `produce` в одном кадре. Парные.
- `pause`/`resume` идемпотентны.
- `status` без side effects.

Нарушение — bug, ловится `contract-tests`.

### Capabilities

```rust
pub struct BackendCapabilities {
    pub source_kind: FrameSourceKind,
    pub resize: ResizePolicy,
    pub input: InputSupport,
    pub damage: DamageSupport,
    pub pause_semantics: PauseSemantics,
    pub content_type_hint: ContentTypeHint,
}

pub enum FrameSourceKind {
    /// CPU-буфер RGBA8. Всегда работает.
    CpuRgba,

    /// Backend уже отрисовал в target, предоставленный в FrameRequest.
    DeviceEncoded,

    /// Статический источник. Renderer кэширует.
    Static,
}

pub enum PauseSemantics {
    Freeze,          // полная заморозка
    LogicOnly,       // логика идёт, кадры — нет
    Unsupported,
}

pub enum ContentTypeHint {
    None,
    Photo,           // передаётся через content-type-v1
    Video,
}
```

**Заметка по FrameSourceKind:** в 0.1 убран `DmaBuf` вариант. Hardware-accelerated video (с DMA-BUF) — задача 0.2. До тех пор — CPU-path.

### FrameOutput

```rust
pub enum FrameOutput {
    Cpu {
        buffer: Arc<CpuBuffer>,        // RGBA8, row-major, premultiplied
        damage: DamageRegion,
    },
    DeviceEncoded,                      // backend записал в target из FrameRequest
    Unchanged,                          // ничего не изменилось
    SkippedDegraded(SkipReason),
}
```

`Unchanged` критичен для статики и idle — Renderer не делает present.

---

## 4. Контракт `Renderer`

```rust
pub trait Renderer {
    fn surface_format(&self) -> SurfaceFormat;
    fn surface_size(&self) -> SurfaceSize;

    /// Проверка совместимости с backend до prepare.
    /// Чистая функция.
    fn negotiate(&self, caps: &BackendCapabilities) -> NegotiationResult;

    /// Единственная точка создания GPU-ресурсов.
    fn allocate(&mut self, req: &ResourceRequest)
        -> Result<ResourceHandles, AllocError>;

    /// Презентация в surface.
    fn present(&mut self, frame: FrameOutput)
        -> Result<PresentOutcome, PresentError>;

    fn status(&self) -> RendererStatus;
}
```

**Нет `DeviceKind`** — только один stack (wgpu). Если в Фазе II появится второй — это contract-change, тогда enum добавится.

### Правила

- Renderer **не владеет** Backend. Владение на уровне OutputRuntime.
- `allocate` — единственная точка создания GPU-ресурсов.
- `negotiate` — чистая функция.
- Renderer не знает про Wayland выше уровня «у меня есть surface».

---

## 5. Контракт `wpe-compat` и LoadReport

### LoadReport

```rust
pub struct LoadReport {
    pub status: LoadStatus,
    pub capabilities_effective: BackendCapabilities,  // после degradation
    pub warnings: Vec<CompatWarning>,
    pub ignored: Vec<IgnoredItem>,
    pub asset_stats: AssetStats,
}

pub enum LoadStatus {
    Ok,
    Partial { severity: PartialSeverity },
    Failed(LoadError),
}

pub enum PartialSeverity {
    Cosmetic,
    Visible,
    Major,
}
```

### SupportMatrix

Типизированная матрица в `wpe-compat`:

```rust
pub enum SupportLevel {
    Unsupported,
    Detected,
    Partial,
    Full,
}

pub struct SupportMatrix {
    pub image_formats: BTreeMap<ImageFormat, SupportLevel>,
    // video_codecs — добавляется если video backend прошёл stretch gate (CHARTER §13).
    // Иначе — поле отсутствует в 0.1 SupportMatrix, появляется в 0.2.
    pub video_codecs:  BTreeMap<VideoCodec, SupportLevel>,
    // shader_features — FUTURE, в 0.2 scope. В 0.1 репозиторий не содержит
    // ни типа ShaderFeature, ни этого поля. TODO 0.2.
    // pub shader_features: BTreeMap<ShaderFeature, SupportLevel>,
}
```

В 0.1 содержимое узкое:
- **image** (PNG, JPG, WebP — Full) — обязательно.
- **video** (H.264, H.265, VP9, AV1 через ffmpeg — Full) — **только при прохождении stretch gate**, иначе matrix не содержит video_codecs в 0.1 вовсе.
- **shader** — отсутствует в матрице 0.1 полностью. Тип `ShaderFeature` и поле `shader_features` появляются в 0.2.

### Правило публикации метрик

Числовые метрики покрытия корпуса — **только** на основе `LoadReport` от реального запуска. Матрица — декларация, reports — реальность.

---

## 6. Fallback Policy

Для 0.1 таблица минимальна. Полная таблица — в будущем `FALLBACK-POLICY.md`.

| Категория | Действие | Severity |
|---|---|---|
| Image format unsupported | Error load, не грузить | — |
| Image smaller than output | Upscale + warning [W001] | Cosmetic |
| Image EXIF broken | Игнорировать EXIF, загрузить | Cosmetic |
| Video codec unsupported (если video входит в 0.1) | Error load | — |
| Video resolution huge (если video входит в 0.1) | Downscale warning [W010] | Cosmetic |

**Shader rows** — не в 0.1, добавляются в fallback policy в 0.2 вместе с shader backend. Shader compile errors, undefined uniforms, GPU hang protection — это 0.2 scope.

Расширяется с новыми backends.

---

## 7. Контракт времени

```rust
#[derive(Copy, Clone)]
pub struct RuntimeInstant(u64);  // наносекунды с запуска

pub struct FrameDelta(Duration);

pub struct RuntimeState {
    pub now: RuntimeInstant,
    pub frame_index: u64,
    pub paused: bool,
    pub input: InputSnapshot,
    pub output_geometry: OutputGeometry,
    pub fullscreen_inhibit: bool,
}
```

Запрещено в backend:
- `std::time::Instant::now()` для логики.
- Системное время для анимаций.
- `std::env::var` во время `update`/`produce`.

---

## 8. Контракт ошибок

```rust
pub enum LoadError {
    ManifestInvalid(String),
    AssetMissing(PathBuf),
    FormatUnsupported { found: String, supported: Vec<String> },
    NegotiationFailed(NegotiationError),
    Io(std::io::Error),
}

pub enum BackendError {
    Decoder(DecoderError),
    ResourceExhausted,
    InvalidState(&'static str),  // bug
}

pub enum PresentError {
    SurfaceLost,                  // recreate Surface
    DeviceLost,                   // recreate OutputRuntime
    Transient,                    // retry next frame
}
```

**Обработка:**
- `LoadError` → fallback (solid color), IPC возвращает ошибку.
- `BackendError::InvalidState` — bug, ERROR log + backtrace, backend → Failed.
- `PresentError::SurfaceLost` — автоматический recreate Surface, один раз.
- `PresentError::DeviceLost` — OutputRuntime пересоздаётся целиком.

`panic!` запрещён. `unreachable!` — только в недостижимых match с safety comment.

---

## 9. Потокобезопасность

> ⚠️ **PROTOTYPE-PENDING — текст ниже устарел.**
>
> Этот раздел описывает threading model, которую я **не проверял на реальной
> машине**. SELF-AUDIT.md Gap 1 и `prototype-main.rs` показали, что правильная
> модель — **calloop-first**, не tokio-first.
>
> **Что мы теперь знаем (из прототипа, pending verification на ПК):**
> - Main thread = `calloop::EventLoop`.
> - Wayland events интегрируются через `calloop-wayland-source::WaylandSource`.
> - wgpu render вызывается **внутри callback'ов** calloop — тот же thread.
> - Один thread на весь daemon в 0.1.
> - Tokio **не нужен** для 0.1 (никакого async I/O пока нет).
>
> **Когда переписывается:**
> После запуска `prototype-main.rs` на wlroots-компизиторе (Hyprland / Sway /
> labwc / river / niri). Команда: `cargo run --release`. Измеряется CPU в idle,
> memory footprint, startup time. По факту обновляется §9 с реальными числами
> и фактической архитектурой.
>
> **Если прототип покажет, что calloop-first не справляется** (например,
> heavy image decode блокирует main thread больше чем на frame budget):
> добавляется secondary thread с tokio или просто std::thread::spawn для
> конкретной задачи (decode), с mpsc обратно в calloop. Но это реактивное
> добавление, не «tokio с первого дня».
>
> **Старый текст ниже оставлен для диффа, но не является руководством:**

~~- `Daemon` — main thread, tokio runtime.~~
~~- `WaylandConnection` — отдельный thread с `calloop`.~~
~~- `Backend::prepare` — tokio blocking pool (может быть долгим).~~
~~- `Backend::update`/`produce`, `Renderer::*` — **только** в render-thread своего OutputRuntime.~~
~~- Один render-thread = один OutputRuntime.~~
~~- IPC server — tokio. Команды → OutputRuntime через `tokio::sync::mpsc`.~~
~~- `SharedAsset` — только `Arc<T>` с immutable данными.~~

Проверки (эти остаются актуальными независимо от threading model):
- `#[forbid(unsafe_code)]` везде кроме явных FFI (`wpe-backend-video/ffmpeg_ffi` в 0.2 если будет).
- `#[deny(clippy::await_holding_lock)]` — применимо только если async появится.
- `panic!` запрещён в production коде.

---

## 10. Wayland Integration Contract

Новый раздел для 0.1. Scope строго определён.

### Протоколы и их обработка

```rust
pub enum WaylandProtocol {
    /// Обязательный для 0.1. Нет — не работаем.
    LayerShell,
    /// Обязательный для 0.1. Нет — не работаем.
    XdgOutput,
    /// Желательный в 0.1. Нет — integer scaling fallback + [W023].
    /// **Обязательная pair:** `Viewporter`. Fractional scale без viewporter
    /// означает downscale на стороне композитора = мыло. Если FractionalScale
    /// присутствует, а Viewporter нет — регистрируем [W024] и откатываемся
    /// на integer scaling, как если бы fractional не было. Это не академическая
    /// тонкость: wp-fractional-scale-v1 спецификация прямо предполагает, что
    /// клиент подаёт масштабированный буфер через wp_viewport, keep wl_surface
    /// buffer_scale = 1.
    FractionalScale,
    /// Обязательная pair к FractionalScale. Без него fractional scaling не работает.
    /// Отдельно от FractionalScale также полезен (crop/scale для image fit modes),
    /// но в 0.1 используется только как pair к fractional.
    Viewporter,
    /// Желательный в 0.1. Нет — не передаём hint.
    /// В 0.1 — только статический `photo` для image; `video` hint добавляется
    /// если video прошёл stretch gate (CHARTER §13).
    ContentType,
    /// Желательный в 0.1. Нет — binary fullscreen detection отключен + [W040].
    /// Не фундамент — отсутствие не ухудшает базовый image-only сценарий.
    ForeignToplevelList,
    // IdleNotify — ПЕРЕНЕСЁН В 0.2 вместе с pause-on-idle.
    // Enum variant НЕ добавляется в 0.1 вообще. Warning W041 не существует в 0.1.
    // Detector не проверяет этот протокол в 0.1.
    // Возвращается в этом enum в 0.2 вместе с реализацией pause-on-idle.
}
```

### Observational notes (не в enum, не contract)

**`presentation-time`** — протокол feedback о фактическом времени презентации кадра.
Полезен для честного frame pacing video backend в 0.2. В 0.1 не используется
(image backend не требует точного timing'а, video stretch использует тайминг ffmpeg
декодера). В enum добавляется в 0.2 как пара к HW accelerated video.

**Compositor-specific behaviours (observations, not code):**
- **Hyprland** шлёт `preferred_scale` event сначала как 1x (120), потом corrects
  на реальный. Первый кадр image может быть blurry если не отложить present
  до receipt of scale event OR 100ms timeout.
- **niri** имеет `place-within-backdrop` layer-rule и separate background
  per workspace. Наш daemon использует стабильный namespace `wpe-wallpaper`
  для layer-surface — пользователи niri могут ссылаться на него в layer-rules.
- **`xx-fractional-scale-v2`** экспериментальный в некоторых compositors
  (KDE Plasma 6.7+). В 0.1 мы его не используем, warning о наличии версии 2
  при отсутствии поддержки — **не** добавляется в 0.1 diagnostic catalog.

### Compositor detection

При старте daemon определяет композитор (через XDG_CURRENT_DESKTOP, имя process ID 1 в session, запрос `wl_registry`). Известные композиторы с особенностями — явно перечислены в `wpe-wayland/known_compositors.rs`.

Неизвестный композитор — не ошибка. Работаем по протоколам, которые он предоставляет.

### Graceful protocol degradation

Каждая фича Platform Core должна работать (или явно не работать с сообщением) при отсутствии optional протокола. Таблица в `docs/wayland-protocols.md` (пишется в 0.1).

---

## 11. Что запрещено добавлять без contract-change

- Новый вариант `FrameSourceKind`.
- Новое поле в `BackendCapabilities`.
- Публичный метод в `FrameSource` или `Renderer`.
- Зависимость `wpe-backend-*` от `wgpu`.
- Зависимость `wpe-render-core` от конкретного Wayland протокола.
- `panic!` в production.
- Системное время в логике.
- Глобальные mutable синглтоны.
- `DeviceKind` enum (пока в Фазе I).

---

## 12. Что проверяет CI

1. `cargo deny check` — политика зависимостей.
2. `cargo clippy -- -D warnings` с production lint set.
3. `forbidden-imports` — grep-based проверка.
4. `contract-tests` — инварианты жизненного цикла через mock.
5. Golden-tests против corpus-A (seed → working по мере наполнения).
6. Benchmarks: регрессия > +10% блокирует merge.

Production lint set:
```
-D clippy::await_holding_lock
-D clippy::panic
-D clippy::unwrap_used
-D clippy::expect_used     # кроме тестов
-D clippy::large_futures
-W clippy::cognitive_complexity
```

---

## 13. Процесс изменения контракта

1. Issue `contract-change`: мотивация, альтернативы.
2. PR: документ + типы + contract-tests.
3. Approver из `CODEOWNERS`.
4. Запись в `CONTRACTS-CHANGELOG.md`.

Текущая версия: **v2.0 draft**. До зелёного CI с contract-tests — draft.

---

## 14. Документы, которые сюда не входят

- `IPC.md` — протокол демон↔CLI/GUI.
- `CONFIG.md` — формат конфига.
- `CORPUS.md` — структура и правила corpus-A.
- `FALLBACK-POLICY.md` — полная таблица.
- `WAYLAND.md` — детали интеграции.
- `DIAGNOSTIC-CODES.md` — каталог warning codes.

Эти документы ссылаются на RUNTIME.md, не наоборот.

---

## 15. Changelog

- **v2.0 draft (current)** — переписано после pivot на platform подход и Product Charter 0.1. Отличия от v1.0:
  - Убран `DeviceKind` — только один render stack (wgpu).
  - Убран `FrameSourceKind::DmaBuf` из 0.1 (возвращается в 0.2 с HW accel).
  - Убран раздел про `wpe-backend-scene` (анти-мини-движок) — сцен в Фазе I нет.
  - Убран Reference Hierarchy (Native / LinuxWpengine) — визуальных сравнений в Фазе I нет.
  - Добавлен §10 Wayland Integration Contract.
  - Упрощена SupportMatrix под 0.1 scope.
- **v1.0 draft** — архивирована.
