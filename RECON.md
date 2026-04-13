# Recon Report — Ecosystem Survey (Archived)

Статус: **archived reference**. Снимок экосистемы wallpaper tools на апрель 2026. Аналитический документ, который повлиял на финальные решения в [PROJECT.md v2.0](./PROJECT.md) и [CHARTER-0.1.md](./CHARTER-0.1.md).

**Важно:** рекомендации в §6-8 этого документа — исторические. Часть из них была принята, часть отвергнута после дальнейшего critique. Актуальные решения — в PROJECT.md и CHARTER-0.1.md, не здесь.

Документ обновляется только через `recon-refresh` PR (не чаще раза в год), чтобы отражать изменения в экосистеме.

---

## 1. Карта экосистемы

### 1.1. Wayland wallpaper daemons (прямые аналоги)

| Проект | Язык | Стек | Статус | Scope |
|---|---|---|---|---|
| `swww` | Rust | smithay-client-toolkit, CPU caching | **Архивирован 2025** → `awww` | Images + GIFs, runtime-switchable |
| `awww` | Rust | Форк swww | Живёт | Same as swww |
| `hyprpaper` | C++ | Hyprland-native, IPC | **Ломает API late 2025** | Images, preload/unload |
| `mpvpaper` | C | libmpv, layer-shell | Живёт | Videos only |
| `swaybg` | C | Простейший | Живёт | Static images, no IPC |
| `wbg` | C | Минималист | Живёт | Single static image |
| `wpaperd` | Rust | Own, HW-accelerated transitions | Живёт | Images + transitions |
| `wlrs` | Rust | wgpu + Lua + TOML manifests | Маленький (16★), rewrite | Images + GLSL shaders |
| `linux-wallpaperengine` | C++ | OpenGL, XRandr/layer-shell | Живёт, ~25% WE compat | WE `.pkg` runtime |

### 1.2. Wayland wallpaper GUI frontends

| Проект | Подход |
|---|---|
| `waypaper` | Python GUI, backend-agnostic (swaybg/awww/hyprpaper/mpvpaper/linux-wallpaperengine) |
| `waytrogen` | Rust GTK4, frontend к нескольким backends |
| `awtwall` | TUI picker для Wayland |
| `linux-wallpaperengine-gui` | Specifically для linux-wallpaperengine |

### 1.3. Cross-platform / Windows-focused

| Проект | Ключевая идея | Источник инсайтов |
|---|---|---|
| Wallpaper Engine | Проприетарный `.pkg`, scene graph, custom HLSL | То, от чего мы решили уйти |
| Lively Wallpaper | WinUI 3 + mpv + CEF + Unity/Godot | Grid pause detection, audio API, ML API |
| ScreenPlay | Qt6 + QML + Steam Workshop | QML как native wallpaper format |
| Rainmeter | Skins, Lua, system info widgets | Extensible widgets как pattern |

### 1.4. Околопроектная экосистема

- **wallust** — палитра из изображения (Rust). Для theming integration.
- **matugen** — Material You generation. Такой же класс.
- **pywal** — палитра + template applying. Шире scope (применяет к GTK/terminals).
- **glava** — OpenGL audio visualizer, X11 only.
- **Hidamari** — Python video wallpaper (X11/GNOME).
- **Komorebi** — Linux animated wallpapers с web support.

---

## 2. Ключевые наблюдения

### 2.1. Экосистема нестабильна

`swww` архивирован в 2025, продолжен как `awww`. `hyprpaper` прошёл rewrite с поломкой конфигов и IPC late 2025. Это не исключение — это **паттерн**. Wallpaper tools часто одиночные, maintainer выгорает или интересы меняются, и проект умирает / ломается.

**Вывод для нас:** rule "минимум 2 active maintainers" в CHARTER-0.1 §10 — прямое следствие. И fokus на stability (т.е. продукт, который не ломает конфиги пользователей) — конкурентное преимущество.

### 2.2. Фрагментация scope

Каждый tool делает **одну вещь**. Нет integrated experience:
- Статика: `swaybg`, `wbg`, `awww`.
- Видео: `mpvpaper`.
- Анимация/transitions: `wpaperd`, `awww`.
- Shaders: `wlrs`, `glpaper`.
- WE compat: `linux-wallpaperengine`.
- GUI: `waypaper` (агрегатор).

Пользователь, которому нужны три типа обоев, ставит три демона и один frontend. Fragile и уродливо.

**Вывод для нас:** объединение image/video/shader в одном daemon — реальная ценность, не надуманная.

### 2.3. Frontend-first подход уже существует

`waypaper` показывает, что пользователям нужна единая точка управления. Агрегатор поверх backends — жизнеспособная модель.

**Вывод для нас:** изначально двигало к идее «платформа как оркестратор». Но (см. §3) эта идея была пересмотрена — мы делаем integrated daemon с native backends, не frontend agregator.

### 2.4. Собственный format vs реверс

ScreenPlay успешен с QML. Lively успешен с HTML/WebGL. `linux-wallpaperengine` частично совместим с WE, но «~25% совместимости» — это low ceiling.

**Вывод для нас:** собственный native format (Tier D+E) перспективнее, чем WE compat. WE compat — через adapter в Фазе II, не через собственный runtime.

### 2.5. Недооценённая ценность диагностики

Ни один из существующих tools не имеет first-class diagnostics. Ошибки обычно — «it doesn't work» в stderr. User troubleshooting — через GitHub issues.

**Вывод для нас:** actionable diagnostic (CHARTER-0.1 §8) — одно из главных конкурентных преимуществ.

---

## 3. Архитектурные паттерны, которые мы изучили

### 3.1. Layer-based композиция (из wlrs)

Пример из `wlrs` manifest.toml:

```toml
[[layers]]
name = "background-color"
content = "#000033"
z_index = -1000

[[layers]]
name = "wave-effect"
content = "assets/background.png"
effect_type = { shader = "wave" }
z_index = 500
params = { amplitude = 0.9, frequency = 0.4, speed = 2.0 }
```

Мощный паттерн. В CHARTER-0.1 **не** включён — layered composition это 0.4. В 0.1 один wallpaper = один слой.

### 3.2. Framerate vs tickrate (из wlrs)

```toml
framerate = 30
tickrate = "compositor"
```

Разделение визуальной частоты и логической. В CHARTER-0.1 не формализовано как config, но в RUNTIME.md отражено через `update` vs `produce` separation.

### 3.3. Grid-based pause detection (из Lively)

Три уровня стратегий: grid (tiles покрытия), foreground processes, Direct3D exclusive. В 0.1 — только binary fullscreen (§4 CHARTER-0.1). Grid — 0.2.

### 3.4. Hot reload (из ScreenPlay)

Live-editing обоев без перезапуска daemon. В 0.1 — для shaders (CHARTER-0.1 §2). Для image/video не обязательно в 0.1.

### 3.5. Embedded scripting (из wlrs/Lively/Rainmeter)

Lua или similar для animation / reactivity. В 0.1 — нет (CHARTER-0.1 §4). Lua — 0.5 (PROJECT.md §5).

---

## 4. Wayland протоколы, которые были пропущены

Изначальный план упоминал layer-shell, foreign-toplevel, idle-notify. Добавлены после recon:

| Протокол | Для чего | Когда |
|---|---|---|
| `wp-fractional-scale-v1` | Корректный HiDPI (125%, 150%) | **0.1, обязательный** |
| `content-type-v1` | Hint `photo`/`video` композитору | **0.1** |
| `wlr-output-power-management-v1` | Pause при выключении монитора | 0.2 |
| `ext-image-copy-capture-v1` | Screenshots через композитор | 0.3 (для GUI previews) |

Подробнее — RUNTIME.md §10.

---

## 5. wlrs — разбор и решение

`wlrs` (WERDXZ/wlrs) — ближайший проект на Rust. 16 stars, 20 commits, daemon в процессе rewrite. Стек почти идентичный нашему: wgpu + smithay-client-toolkit + TOML manifests.

Что у wlrs есть:
- Layer system с z-index.
- Встроенные шейдеры (wave, glitch, gaussian).
- Multi-monitor.
- CLI + IPC.

Чего у wlrs нет:
- Video backend.
- Profile system.
- Contract discipline / testing infrastructure.
- Diagnostic system.
- HW video decoding.

**Принятое решение (PROJECT.md D8):** не fork, не активная collaboration. Сосуществование. Разные акценты: они — runtime + effects, мы — platform + stability + profiles.

---

## 6. Что изменилось в проекте после recon

Конкретные правки, которые были сделаны:

### 6.1. Добавлено в scope

- `wp-fractional-scale-v1` как обязательный протокол в 0.1.
- `content-type-v1` hints в 0.1.
- Grid-based pause detection как отдельный tier (перенесён в 0.2).
- Layered composition как отдельный tier (0.4).
- Lua scripting как отдельный tier (0.5).
- Palette extraction + hooks (0.3).
- Audio-reactive (0.6).

### 6.2. Убрано из scope

- `wpe-render-gl` (второй render stack) — после отказа от собственного WE runtime.
- Собственный WE scene runtime — **навсегда**.
- Live2D integration — навсегда (licensing).
- Godot integration — навсегда (complexity).
- Web wallpapers — навсегда (WebKit2GTK ≠ Chromium).

### 6.3. Пересмотрено

- Fokus с «WE compat» на «native engine + eventual adapter в Фазе II».
- Платформа/оркестратор идея — принята в общих чертах, но adapter layer отложен в Фазу II.
- Reference Hierarchy (Native / LinuxWpengine) — убран из RUNTIME.md (визуальных сравнений в Фазе I нет).

---

## 7. Рекомендации, которые **не** были приняты

Для исторической честности: часть recon §6-8 изначального отчёта была отвергнута после дальнейшего критического прохода.

- **«Сделать backend SDK сразу»** — отвергнуто. SDK — Фаза II. В Фазе I native backends — часть Core.
- **«Adapter к mpvpaper в первой линии»** — отвергнуто. Adapter layer целиком — Фаза II.
- **«Platform-orchestrator as main positioning»** — отвергнуто в пользу «узкое крепкое ядро в 0.1, платформа в 2.0».

Причина отвержений — риск feature creep и diffusion focus. Platform approach правилен как long-term, но опасен как стартовая позиция.

---

## 8. Что продолжает наблюдаться

Темы для потенциального recon-refresh (не раньше чем через год):

- **Будет ли wlrs ещё жив.** Если да — проверить, нужны ли ещё границы D8 PROJECT.md.
- **Стабилизируется ли awww.** Swww-форк может стать новой точкой consolidation.
- **Cosmic wallpaper story.** У Cosmic DE свой wallpaper runtime в разработке — он может изменить landscape.
- **KDE WE plugin evolution.** Если KDE разберётся с scene types — это снизит нужду в нашем Фазе II.
- **Wayland protocols evolution.** Могут появиться новые relevant protocols.

---

## 9. Ссылки (snapshot April 2026)

### Проекты

- wlrs — https://github.com/WERDXZ/wlrs
- swww (archived) — https://github.com/LGFae/swww
- awww — (форк, актуальные ссылки в AUR)
- hyprpaper — https://github.com/hyprwm/hyprpaper
- mpvpaper — https://github.com/GhostNaN/mpvpaper
- wpaperd — https://github.com/danyspin97/wpaperd
- linux-wallpaperengine — https://github.com/Almamu/linux-wallpaperengine
- Lively Wallpaper — https://github.com/rocksdanister/lively
- ScreenPlay — https://gitlab.com/kelteseth/ScreenPlay
- waypaper — https://github.com/anufrievroman/waypaper

### Wayland protocols

- content-type-v1 — https://wayland.app/protocols/content-type-v1
- fractional-scale-v1 — https://wayland.app/protocols/fractional-scale-v1
- ext-idle-notify-v1 — https://wayland.app/protocols/ext-idle-notify-v1
- ext-foreign-toplevel-list-v1 — https://wayland.app/protocols/ext-foreign-toplevel-list-v1

### Libraries

- smithay-client-toolkit — https://github.com/Smithay/client-toolkit
- wgpu — https://github.com/gfx-rs/wgpu
- ffmpeg-next — для video decoding
- wallust / matugen — как примеры для theme hooks

---

## 10. Changelog

- **v1.0 archived (current)** — первый и единственный recon. Повлиял на PROJECT.md v2.0 и CHARTER-0.1.md. Рекомендации §6 отражают final decisions.
