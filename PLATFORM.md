# Platform Boundaries

Статус: **v1.0 stable**. Документ границ Platform Core vs всё остальное.

Этот документ отвечает на один вопрос: **что входит в Platform Core, а что — нет**. Он нужен, потому что проекты такого рода (с profiles, palette, adapters, hooks) склонны разрастаться неконтролируемо. Без чёткой границы Platform Core через год превращается в мини-OS.

Связанные: [CHARTER-0.1.md](./CHARTER-0.1.md), [PROJECT.md](./PROJECT.md), [RUNTIME.md](./RUNTIME.md).

Изменение границы — PR с меткой `platform-boundary-change` и обоснованием, почему новая граница всё ещё удовлетворяет принципу «Platform Core должна быть самодостаточна без адаптеров и hooks».

---

## 1. Главный принцип

**Platform Core должна быть самодостаточна без адаптеров, без hooks, без third-party backends, без Lua.**

Если убрать всё расширяемое — продукт должен оставаться полезным и сильным. Это тест здоровья архитектуры. Если убрать hooks → и остался бесформенный caller — значит, hooks стали заменой функциональности, а не расширением.

Конкретно для 0.1: убрали бы мы сейчас profile hooks (которых нет), adapter layer (которого нет), Lua (которого нет), palette (которой нет) — и продукт всё ещё работает. Это и есть 0.1 CHARTER. Мы строим самодостаточный minimum.

---

## 2. Три слоя

```
┌─────────────────────────────────────────────────────┐
│  Слой 3: Расширения                                 │
│  ─────────────────                                  │
│  • Adapters (Фаза II)                               │
│  • Third-party backends (Фаза II)                   │
│  • User hooks (palette hooks в 0.3)                 │
│  • Lua wallpaper scripts (0.5)                      │
└─────────────────────────────────────────────────────┘
                          ↕
┌─────────────────────────────────────────────────────┐
│  Слой 2: Backend API (SDK)                          │
│  ─────────────────────────                          │
│  • FrameSource / LayerSource traits (позже)         │
│  • AdapterBackend trait (Фаза II)                   │
│  • Capability negotiation protocol                  │
│  ⚠ В Фазе I — internal only. В Фазе II — public.   │
└─────────────────────────────────────────────────────┘
                          ↕
┌─────────────────────────────────────────────────────┐
│  Слой 1: Platform Core                              │
│  ─────────────────────                              │
│  • Daemon + Event Loop                              │
│  • Wayland Integration                              │
│  • Profile System                                   │
│  • IPC Server                                       │
│  • Diagnostics System                               │
│  • Config Store                                     │
│  • Native Backends: image (must-have), video (stretch, §13)│
│                                                     │
│  GUI — НЕ в Platform Core (mainstream pattern:      │
│  daemon и GUI раздельны, см. §2 ниже).              │
└─────────────────────────────────────────────────────┘
```

### Слой 1 — Platform Core

**Что входит:**

- **Daemon** — главный процесс, event loop, lifecycle.
- **Wayland Integration Layer** — layer-shell, output management, hotplug, fractional-scale, content-type hints, foreign-toplevel. `idle-notify` — **не в 0.1**, приходит в 0.2 вместе с pause-on-idle.
- **Profile System** — управление профилями (создание, переключение, хранение, применение).
- **IPC Server** — Unix socket, JSON protocol, request routing.
- **Diagnostics System** — сбор состояния, форматирование для CLI, structured logging.
- **Config Store** — чтение/запись TOML конфигов, XDG paths, migration between versions.
- ~~**Minimal GUI**~~ — **вне Platform Core**. Mainstream pattern экосистемы: daemon и GUI раздельны (swaybg/wpaperd/hyprpaper/mpvpaper — ни один не имеет встроенного GUI). Пользователь управляет через `wpectl` CLI. Existing GUIs (waypaper, hyprwall) могут интегрироваться через наш IPC. Возможно — отдельный sub-project `wpe-gui` после 0.1 stable.
- **Native Backends** — image (must-have в 0.1), video (stretch goal в 0.1 с date-gate, иначе в 0.2). Shader backend — **в 0.2**, не в 0.1. Все они — **часть Core**, не плагины.

**Что не входит:**

- Rendering of specific wallpaper types beyond three native — это слой 3.
- Activation rules beyond manual profile switch (time, app, battery) — это слой 3 (в 0.4+).
- Palette extraction algorithms — это слой 3 (в 0.3+).
- Any subprocess supervision — это слой 3 (Фаза II).

### Слой 2 — Backend API (SDK)

**В Фазе I (0.x):** внутренний только. `FrameSource` и связанные traits существуют, но не являются публичным API. Мы можем их менять между релизами.

**В Фазе II (2.x):** становятся public API. Semver-stable. Изменение — breaking change в `wpe-sdk` crate.

**Что сюда входит:**

- Traits: `FrameSource`, `LayerSource` (в 0.4), `AdapterBackend` (в 2.0).
- Типы capabilities: `BackendCapabilities`, `LoadReport`, `CompatWarning`.
- Resource handles: `TextureHandle`, `BufferHandle`.
- Что **не** входит: конкретные protocol definitions, Wayland-specific types, GUI widgets.

### Слой 3 — Расширения

**Adapters, hooks, third-party backends, user scripts.** Живут **вне** Core binary. Имеют свой lifecycle.

**Гарантии Core → Слой 3:**
- Stable contract (в Фазе II).
- Diagnostic visibility (Core всегда знает и показывает, что происходит с расширениями).
- Graceful handling of failures (если расширение крашнулось, Core не падает).

**Гарантии Слой 3 → Core:** никаких. Расширения могут быть buggy, медленными, исчезающими. Core должен работать **в отсутствие любого расширения**.

---

## 3. Правила границы

### Правило B1. Core не зависит от Слоя 3

Никаких feature flags в Core, которые требуют конкретное расширение. Конфиг `wallust_integration = true` **запрещён** — вместо этого есть общие palette hooks, и пользователь настраивает свой `wallust` сам.

### Правило B2. Слой 3 не может аллоцировать Core-resources напрямую

Расширение, которое хочет получить GPU-текстуру, должно попросить Core через Backend API. Никакого прямого доступа к `wgpu::Device`. Это защищает от GPU resource leaks в buggy adapters.

### Правило B3. Failure изоляция

- Native backend crash → OutputRuntime recreated, остальные работают.
- Adapter crash (Фаза II) → помечается failed, Core продолжает.
- Hook script hangs → timeout, kill, log warning, Core продолжает.
- GUI crash (если вообще будет существовать как sub-project) → daemon работает через CLI/IPC. В 0.1 GUI отсутствует, этот failure mode неприменим.

Compromise: daemon crash = всё не работает. Это неизбежно, но тогда systemd user unit перезапускает daemon, и **последнее состояние восстанавливается** из `~/.local/state/wpe/`.

### Правило B4. Extension points имеют явные protocol versions

Каждая точка расширения (IPC, palette DBus signal, hook script interface) версионирована. Breaking change — bump протокола, старая версия работает параллельно в течение N релизов.

### Правило B5. Diagnostic обязательна для каждого расширения

Если у нас есть adapter к X, `wpectl status --verbose` должен показывать:
- Что adapter установлен.
- Его версия.
- Его текущий pid / health.
- Последнее сообщение об ошибке, если было.

Невидимое расширение — запрещено.

---

## 4. Profile System — где границы

Profile — сложная сущность, которая может разрастись в мини-OS. Жёсткая декомпозиция, чтобы этого не случилось.

### Данные профиля разделяются на **четыре независимых сущности**

1. **Profile** — что рисуется (wallpaper per output, backend, fit).
2. **RuntimePolicy** — как рисуется (pause rules, FPS caps, battery behavior).
3. **ActivationRule** — когда рисуется (manual, time, app). В 0.1 — только manual.
4. **Hooks** — что происходит вокруг (palette hooks, transition hooks). В 0.1 — нет.

Это **четыре разных типа в коде**, не одна структура с кучей Optional полей.

```rust
// 0.1 — только первые две:
pub struct Profile {
    pub name: String,
    pub outputs: HashMap<OutputName, WallpaperAssignment>,
}

pub struct RuntimePolicy {
    pub pause_on_fullscreen: bool,
    // pause_on_idle: Option<IdleConfig> — ДОБАВЛЯЕТСЯ В 0.2 вместе с
    // ext-idle-notify-v1 и pause-on-idle feature. Не в 0.1.
}

// 0.4+:
pub struct ActivationRule { /* manual | time | app_foreground | battery */ }

// 0.3+:
pub struct Hooks {
    pub on_palette_change: Option<PathBuf>,
    pub on_activation: Option<PathBuf>,
}
```

Каждая сущность эволюционирует независимо. В UI они могут сходиться в одном экране «настройки профиля», но в модели данных — раздельны.

### В 0.1 profile имеет **только**:

- Name, description.
- Outputs → wallpaper assignments (path, backend, fit).
- RuntimePolicy (pause_on_fullscreen). Без `pause_on_idle` — это 0.2.

Всё остальное — **запрещено** (см. CHARTER-0.1 §7).

---

## 5. Theme Integration — hook point, не implementation

Тема, которая чаще всего превращает wallpaper tools в мини-OS. Жёсткая позиция:

### Что мы делаем (0.3)

- Извлекаем палитру из текущих обоев (dominant color + accent, 4-6 цветов).
- Публикуем в `~/.cache/wpe/palette.json` при каждой смене обоев.
- Рассылаем DBus signal `dev.wpe.PaletteChanged` с содержимым палитры.
- Запускаем user-defined hook script если указан: `~/.config/wpe/hooks/on-palette-change.sh`.
- Hook получает палитру через stdin (JSON) или через env variables.

### Что мы **не** делаем

- Не применяем палитру к GTK/Qt.
- Не модифицируем GTK themes / Qt styles.
- Не генерируем terminal color schemes.
- Не применяем к editor themes.
- Не знаем, что такое accent color для конкретного DE.
- Не предоставляем шаблоны (templates) для генерации конфигов.

### Почему так жёстко

Потому что:
1. Эта часть имеет десятки корректных implementations (`wallust`, `matugen`, `pywal`, custom scripts). Выбирать один — неправильно.
2. DE-specific integration невозможна без знания конкретного DE. Мы wlroots-only, но композиторы бывают разные.
3. Theme integration — это **политика**, а не механизм. Пользователь знает свои предпочтения.

### Правильный workflow для пользователя

```bash
# Пользователь устанавливает matugen.
# Пользователь пишет свой hook:
cat > ~/.config/wpe/hooks/on-palette-change.sh <<'EOF'
#!/bin/sh
PALETTE_JSON="$1"  # path to palette JSON
matugen image --json "$PALETTE_JSON" --config ~/.config/matugen/config.toml
EOF
chmod +x ~/.config/wpe/hooks/on-palette-change.sh

# Готово. Мы hook point — они implementation.
```

Это **меньше кода у нас, больше свободы у пользователя**. И это правильно.

---

## 6. Preview / Screenshot Service — НЕ в 0.1

Preview generation (для list/пиктограмм) и screenshots (для debug/sharing) —
**не часть Core 0.1**. CHARTER-0.1 §2 их не перечисляет, и добавлять их
сейчас — feature creep через boundary document.

### Что это значит

- В 0.1 `wpectl` не имеет команды `preview` или `screenshot`.
- Third-party GUIs (waypaper, hyprwall), которые будут интегрироваться через
  наш IPC, используют собственную генерацию preview (thumbnail из исходного
  файла) — они это уже умеют.
- `ext-image-copy-capture-v1` в 0.1 daemon не binding'ит.

### Когда добавляется

**0.3 как часть palette extraction feature.** Когда мы уже читаем текущий
wallpaper для извлечения палитры, добавление публикации preview становится
marginal cost. Тогда же добавляется `GetPreview` IPC command.

**Возможно раньше** — если community потребует для своих GUI frontend'ов.
Тогда отдельная minor версия 0.1.x с добавлением preview API, которая **не**
меняет других контрактов.

### Почему вынесено

Preview — это не fundamental wallpaper daemon concern. Daemon знает path
к файлу обоев, thumbnail generation — responsibility GUI consumer'а. Включение
preview в Core добавляет: кэш-инвалидацию, обработку supported formats,
decoder для первого кадра video — это значимый код для feature, который
никто в 0.1 не использует.

---

## 7. Diagnostic System — first-class, не cross-cutting

В других проектах diagnostic часто превращается в просто «logging + occasional status dump». У нас — first-class.

### Требования

- **Structured.** Каждый warning имеет код, контекст, suggestion.
- **Accessible.** `wpectl status --verbose` выдаёт полное состояние.
- **Timely.** Warnings выдаются в момент возникновения, не только при query.
- **Machine-readable.** `wpectl status --json` для скриптов.
- **Causal.** Если backend degraded — видно почему. Если protocol unavailable — видно какой.

### Примеры warning codes

Детали — в `docs/diagnostic-codes.md`. Формат:

```
[W001] Source image smaller than output
  Context: image 1280x720 → output 2560x1440
  Impact:  Upscaling with quality loss
  Fix:     Use image at least 2560x1440 for this display

[W023] fractional-scale-v1 protocol unavailable
  Context: Compositor does not advertise wp_fractional_scale_v1
  Impact:  Fractional display scaling (e.g. 125%) may show artifacts
  Fix:     Update your compositor to support this protocol

[W024] wp_viewporter missing while wp_fractional_scale_v1 is present
  Context: fractional-scale available but viewporter is not
  Impact:  Fractional scaling degrades to integer (image may appear blurry
           on 125%/150% displays — buffer is downscaled by compositor
           instead of being pre-scaled by client)
  Fix:     Update your compositor. wp_viewporter is required pair for
           correct fractional-scale rendering per protocol spec.
```

Пользователь, у которого что-то не работает, должен получать **действующий совет**, а не «Error: failed».

---

## 8. Что Core **не** делает, несмотря на искушения

Список частых ошибок в подобных проектах:

### Не делаем: автодетект типа обоев по файлу

Backend указывается в профиле **явно**. Нет магии `set ocean.mp4 → video backend`. Если пользователь написал `backend = "image"` для `.mp4` — это его выбор (и ошибка будет видна в diagnostic). Автодетект прячет сложность, потом ломается в edge cases.

### Не делаем: Wallpaper Picker с Unsplash/etc

Это прямо конкурирует с Variety Wallpaper Changer и не имеет отношения к нашему scope. Пользователь сам скачивает обои. Мы показываем то, что в его папке.

### Не делаем: автоматическое слежение за папкой и cycling

Это feature `variety`/`waypaper`. Можно сделать в 1.x через activation rules, но не в Core.

### Не делаем: lock screen

Отдельный protocol (`ext-session-lock-v1`), отдельная сущность, отдельная философия. Возможно, когда-нибудь, в отдельном инструменте `wpe-lock`. Не в Platform Core.

### Не делаем: screensaver

Та же причина. Отдельная сущность.

### Не делаем: widgets

Это ScreenPlay / Rainmeter direction. Не наш scope.

### Не делаем: wallpaper editor / authoring tool

Пользователь создаёт обои в своём редакторе (Photoshop, GIMP, Krita, text editor для shaders). Мы — runtime, не authoring.

---

## 9. Как принимать решения о границе

Когда возникает новая фича / предложение, идти по чеклисту:

1. **Может ли продукт работать без этого?** Если да — это не Core. Это Слой 3.
2. **Требует ли это политики, которая зависит от DE/предпочтений?** Если да — hook point, не implementation.
3. **Имеет ли это lifecycle вне одного OutputRuntime?** Если да — это отдельная сущность в Platform, не часть backend.
4. **Это механизм или политика?** Механизмы — Core. Политики — пользователю.
5. **Может ли community сделать это как расширение?** Если да — оставить community.

Если после чеклиста непонятно — **оставить вне Core** и посмотреть, возникнет ли community implementation. Добавить позже проще, чем убрать.

---

## 10. Changelog

- **v1.0 stable (current)** — первая версия. Написана параллельно с PROJECT.md v2.0 и CHARTER-0.1.md на основе recon и multi-pass critique.
