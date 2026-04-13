# wpe-rs — проектные документы

Снимок состояния проекта на момент написания прототипа, до первого запуска на wlroots композиторе.

---

## Статус проекта

**Документация:** ~70% готова. Три раздела в `RUNTIME.md` помечены `PROTOTYPE-PENDING` — переписываются после запуска `prototype-main.rs`.

**Код:** один прототип, ~250 строк, непроверен на реальной машине.

**Следующий шаг:** `cd wpe-prototype && cargo run --release` на Hyprland / Sway / labwc / river / niri.

---

## Файлы по назначению

### 🎯 Главное — читать в этом порядке

1. **[CHARTER-0.1.md](./CHARTER-0.1.md)** — жёсткая рамка первого релиза. Что делаем, что запрещено, date-based cutoff для video. Выше всех остальных документов.

2. **[PROJECT.md](./PROJECT.md)** — двухфазная модель (0.1→1.0, потом Phase II). Архитектурные решения D1-D10. Tier map, roadmap до 1.0.

3. **[PLATFORM.md](./PLATFORM.md)** — граница Platform Core vs extensions. Три слоя, правила границ B1-B5, theme integration как hook point.

4. **[RUNTIME.md](./RUNTIME.md)** — контракты рантайма. ⚠️ Секции §2, §3, §9 помечены `PROTOTYPE-PENDING`, читать с оглядкой на SELF-AUDIT.

5. **[SKELETON.md](./SKELETON.md)** — план первого скелета. 5 crate'ов (включая `wpe-cli` skeleton), 5 contract-тестов, TDD-порядок, `wpe diag` как первый milestone.

### 🔍 Аудиты — перед тем как начинать код

6. **[AUDIT-pre-skeleton.md](./AUDIT-pre-skeleton.md)** — 5 implementation-time находок (wgpu v29 API, MSRV 1.87, ffmpeg-next maintenance, Hyprland initial 1x scale, wp_viewporter pair). 6 явно отвергнутых соблазнов (N1-N6).

7. **[SELF-AUDIT.md](./SELF-AUDIT.md)** — честный self-audit после прототипа. 8 gap'ов, из них 2 критичных (threading model, frame callback). Foundational gap 5 — писал документы до кода.

### 💻 Прототип — throwaway, для проверки Gap 1-4

8. **[prototype/src/main.rs](./prototype/src/main.rs)** — ~250 строк реального кода. calloop-first, layer-shell lifecycle, damage tracking, hybrid GPU handling. **Не скомпилирован** — может потребовать minor правки API.

9. **[prototype/Cargo.toml](./prototype/Cargo.toml)** — минимальный manifest. MSRV 1.87, 6 dependencies (wayland-client, smithay-client-toolkit, calloop, calloop-wayland-source, wgpu 29, pollster).

### 📦 Архив — история итераций

10. **[archive/DIFF-v2.1.md](./archive/DIFF-v2.1.md)** — первые fact-based правки (hyprpaper v0.8, `wpaperd-ipc` pattern).
11. **[archive/DIFF-v2.2.md](./archive/DIFF-v2.2.md)** — unified persona, cut order, D7 anti-abstraction, D10 licensing.
12. **[archive/DIFF-v2.3.md](./archive/DIFF-v2.3.md)** — реальное сокращение scope: GUI out, shader → 0.2, video → stretch.
13. **[archive/RECON.md](./archive/RECON.md)** — snapshot экосистемы April 2026.

---

## Что говорят документы одной фразой

> **wpe-rs** — image-first wallpaper daemon для wlroots-композиторов (Hyprland, Sway, labwc, river, niri, Wayfire), написанный на Rust, с акцентом на стабильность, IPC-управление и actionable diagnostics. Video — stretch goal в 0.1. Shader — в 0.2. GUI — вне Phase I. WE compat — только через external adapter в Phase II, если вообще.

---

## Запуск прототипа

**Требования:**
- Linux с wlroots-based композитором.
- Rust 1.87+ (MSRV из wgpu v29).
- Working GPU driver с Vulkan (Mesa amdgpu/intel — ✓, nouveau — ✓, NVIDIA proprietary — best-effort).

**Команды:**
```bash
# Скопировать папку prototype/ на машину с wlroots компизитором
cp -r /path/to/prototype ~/wpe-prototype
cd ~/wpe-prototype
cargo run --release
```

**Ожидаемый output на правильной машине:**
```
wpe-prototype starting, PID=...
[Gap 1] entering calloop run — single thread, no tokio
[Gap 3] configure received: size WxH, elapsed Nms
[Gap 1] init wgpu on calloop thread (not tokio)
[metrics] frame 1 rendered in Nms
[metrics] frame 2 rendered in Nms
[metrics] frame 3 rendered in Nms
[metrics] total runtime: Nms, frames: 3
prototype done.
```

Плюс тёмно-синий прямоугольник на весь экран на время 3 кадров.

**Что может пойти не так:**
- Mелкие API-несоответствия у wgpu 29 или SCTK 0.19 — я не компилировал код.
- `Surface<'static>` через `mem::transmute` — грязный трюк, в production заменится на `Arc<WlSurface>`.
- На NVIDIA proprietary Vulkan может не подняться — expected, CHARTER §7.

**После успешного запуска:**
- Снимаем `PROTOTYPE-PENDING` блоки в RUNTIME §2, §3, §9.
- Переписываем секции по фактической работающей архитектуре.
- Начинаем настоящий skeleton (`cargo new --lib crates/wpe-compat`).

---

## Как это всё читалось бы с нуля

Если читать первый раз — только 4 документа в таком порядке:

1. CHARTER-0.1 (~20k) — что делаем.
2. PROJECT §1-5 (~8k) — куда идёт проект.
3. SELF-AUDIT §1-5 (~5k) — чего я не знаю.
4. prototype/src/main.rs (~10k) — реальный код.

Остальное — для когда пишешь конкретный компонент.
