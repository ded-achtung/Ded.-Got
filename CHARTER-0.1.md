# Product Charter 0.1

Статус: **v1.0**. Корневой документ первого релиза. **Короче всех остальных, важнее всех остальных.**

Любое изменение — PR с меткой `charter-0.1-change`, минимум один approver из `CODEOWNERS`. После tagging `v0.1.0` этот документ замораживается и становится `CHARTER-0.1.frozen.md`. Будущие charter'ы (0.2, 1.0, 2.0) — отдельные документы, не редактирование этого.

---

## 1. Кто первый пользователь

**Не** разработчик обоев. **Не** WE-рефугий, бегущий с Windows.

Первый пользователь — **wlroots-юзер, который сейчас использует комбинацию из `swaybg` + `mpvpaper` + костыльных скриптов** и хочет:
- Один daemon вместо трёх.
- Предсказуемое поведение после обновлений.
- Разные обои на разных мониторах без ручных wrapper'ов.
- Быструю смену обоев без рестарта.
- Понять из CLI, почему что-то не работает, без чтения страйсов.

Этому пользователю **не нужны** ни WE-обои, ни web-рантайм, ни Live2D. Ему нужен **качественный базовый продукт**, которого в экосистеме нет из-за нестабильности (`swww` архивирован, `hyprpaper` сломал конфиги, `mpvpaper` решает только видео).

Если 0.1 не обслуживает этого пользователя лучше, чем его текущий стек — релиз провалился, независимо от фич.

---

## 2. Что продукт умеет в 0.1 (без адаптеров, без WE)

Минимальный полезный продукт:

**Core Wayland integration.**
- `zwlr-layer-shell-v1` surface на каждом output.
- Multi-output через `wl_output` + `zxdg-output-manager-v1`.
- Hotplug мониторов (добавление/удаление без рестарта daemon).
- `wp-fractional-scale-v1` для корректного HiDPI.
- `wp-content-type-v1` hint для композитора. В 0.1 — только статический `photo` (image backend всегда, video — если прошёл §13 stretch gate, тогда `video` hint добавляется).

**Native backends.**
- **Image (must-have)**: PNG, JPG, WebP. Режимы fit: `cover`, `contain`, `stretch`, `tile`, `center`.
- **Video (stretch, см. §13)**: MP4/WebM через ffmpeg, **CPU-декодирование**. Loop, mute, speed. Входит в 0.1 только если проходит date-based gate в §13. Иначе — в 0.2 без извинений.
- ~~**Shader**~~ — **перенесён в 0.2**. GLSL/WGSL backend, hot reload, Shadertoy uniforms. Не в 0.1.

**Profile system (минимальный).**
Профиль = `{ per-output-wallpaper-assignment, backend-params }`. Без activation rules, без scheduler, без palette hooks. Один активный профиль одновременно. Переключение через CLI/IPC.

**IPC.**
Unix socket, JSON. Команды: `SetProfile`, `GetActiveProfile`, `ListProfiles`, `GetOutputs`, `Pause`, `Resume`, `Reload`, `Ping`.

**CLI.**
`wpe` как единый бинарь. `wpe profile set`, `wpe output list`, `wpe status`, `wpe diag`.

**GUI.**
~~Минимальный GTK4 или iced-app.~~ **Вне scope Фазы I.** Пользователь управляет через `wpectl` CLI. Существующие GUI (waypaper, hyprwall) могут интегрироваться через наш IPC после стабилизации протокола. Возможно — отдельный sub-project `wpe-gui` после 0.1 stable, если возникнет capacity.

**Pause policy (базовая).**
- Пауза при fullscreen client через `ext-foreign-toplevel-list-v1` (если протокол доступен, иначе graceful degradation).
- ~~Пауза при idle через `ext-idle-notify-v1`~~ — **перенесено в 0.2** вместе с самим протоколом.
- Без battery awareness, без grid detection — всё это 0.2+.

**Diagnostics.**
`wpe diag` — структурированный отчёт: версии Wayland-протоколов на текущем композиторе, какие обои на каком output, текущий FPS, память/CPU, последние 100 событий, warnings.

Всё. Больше — ничего.

---

## 3. Что считается Core (не подлежит выносу в плагины)

**Core — это то, что unit-тестируется внутри monorepo и релизится как единый бинарь.**

- Daemon lifecycle.
- Wayland connection + surface management.
- Output enumeration + hotplug.
- Profile system (persistence, activation, per-output assignment).
- IPC server + client (CLI).
- Native image backend.
- ~~Native shader backend.~~ **Перенесён в 0.2** (см. §2).
- Native video backend (CPU path) — **только как stretch goal**, входит в Core 0.1 только при прохождении date-based gate в §13. Иначе — часть Core 0.2.
- Diagnostics API.
- ~~GUI (может быть отдельным crate, но в том же monorepo, тот же цикл релиза).~~ **Вне Core Фазы I.** См. §2.

Эти компоненты имеют общие контракты, общие типы, общий цикл тестирования. Они релизятся вместе или не релизятся вовсе.

---

## 4. Что запрещено тащить в Core (0.1 и всегда)

Эти запреты — не «пока нет ресурсов». Это **архитектурный критерий**. Если код нарушает их — он **не в Core**, независимо от того, кто его написал и зачем.

**Q1. Никакого знания про internal formats внешних программ.**
Core не знает, что такое `.pkg` от Wallpaper Engine. Не знает mpv IPC-команды. Не знает hyprpaper config format. Всё это — дело adapter'ов в будущих релизах.

**Q2. Никакой supervise external processes.**
Core не запускает subprocess'ы, не мониторит их PID, не парсит их stdout. Есть ровно один процесс — наш daemon.

**Q3. Никакой браузер, никакой scripting runtime, никакой VM.**
В Core нет WebKit, нет Lua, нет WASM, нет JS. Shader — это GLSL/WGSL, декларативно компилируемый один раз при загрузке. Точка.

**Q4. Никакой theming engine.**
Core не генерирует палитры. Не пишет в GTK/Qt settings. Не управляет terminal colors. Не знает про `wallust`/`matugen`/`pywal`. Эти инструменты подключаются пользователем через 0.3+ hook system, **вне** Core.

**Q5. Никакой scheduler, calendar, weather, audio analysis.**
Core не имеет cron-подобной логики активации. Профили в 0.1 переключаются **только вручную**. Никакого «в 18:00 ставить evening profile» в Core 0.1.

**Q6. Никакой знания про не-wlroots композиторы.**
Code paths для GNOME/KDE/COSMIC/Mir **не существуют** в Core. Если понадобится в будущем — через platform abstraction layer, который сейчас не строим.

**Q7. Никакой GPU-heavy compute за пределами wallpaper rendering.**
Core не делает FFT для аудио. Не запускает ML-модели. Не растрирует SVG в рантайме.

**Q8. Никакой WE compat любого вида.**
Ни импорт, ни adapter, ни частичный runtime. В 0.1 слово «Wallpaper Engine» встречается в кодовой базе **ноль раз**, кроме README в секции «что мы не делаем».

---

## 5. Что сознательно отложено

С каждой функцией — **в какой релиз**, не «когда-нибудь».

| Функция | Релиз | Причина отложить |
|---|---|---|
| Layered composition (multiple layers per output) | 0.4 | Нужно сначала стабилизировать single-layer pipeline |
| Lua scripting | 0.5 | Нужна стабильная layer model и property system |
| Palette extraction + hook system | 0.3 | Нужна стабильная profile model |
| Activation rules (time, app, battery) | 0.3 | Часть профилей как first-class concept |
| Hardware video decoding (VAAPI + DMA-BUF) | 0.2 | Оптимизация, не blocking feature |
| Battery-aware FPS | 0.2 | Тот же класс |
| Grid-based pause detection | 0.4 | Требует геометрии окон, сложнее базовой pause |
| Audio-reactive wallpapers | 0.6 | Требует PipeWire integration + FFT |
| Transitions между обоями | 0.3 | Не в MVP, но раньше palette |
| Preview cache | 0.2 | Нужен для GUI, но не для 0.1 MVP |
| Adapter SDK | 1.x (Фаза II) | Отдельная фаза, gate после 1.0 |
| Adapter к `mpvpaper` | 1.x | Зависит от Adapter SDK |
| Adapter к `linux-wallpaperengine` | 1.x | Главная фича 2.0 |
| Web wallpapers | Никогда в Core | Через community adapters в 2.x |
| Godot/Unity integration | Никогда | Out of scope постоянно |
| Live2D | Никогда в Core | Через community adapters в 2.x |
| Не-wlroots композиторы | Никогда в 1.x | Возможно в 3.x, но не обещаем |
| Theming engine | Никогда | Мы hook point, не implementation |

---

## 6. Критерий успеха 0.1

Три независимых gate — functional, quality, performance. Релиз только когда все три зелёные.

**Functional (must-have).**
- Пользователь из §1 ставит разные image-обои на два монитора с разным DPI, переключает профиль через CLI, не замечает утечек памяти за 72 часа на тестовом стенде.
- Hotplug: отключение/подключение монитора без рестарта daemon, обои восстанавливаются корректно.
- Automatic pause on fullscreen работает (если `ext-foreign-toplevel-list-v1` доступен; если нет — `wpe diag` явно это показывает).
- Restart daemon восстанавливает последнее состояние из `~/.local/state/wpe/`.
- `wpe diag` даёт отчёт, по которому можно понять проблему без чтения tracing логов.

**Functional (stretch).**
- Video backend работает на 5 тестовых файлах без leaks (см. §13). Если не проходит — в 0.2 без извинений (см. §12).

**Quality.**
- Zero crashes на corpus A (15 image файлов разных форматов и размеров) при 72-часовом прогоне.
- Zero regressions между 0.1.x patch-релизами (golden tests в CI).
- IPC protocol задокументирован (man page `wpectl.1`) и **не меняется** в 0.1.x.
- `cargo clippy -- -D warnings` зелёный. Forbidden-imports lint зелёный.

**Performance.**
- Статический image: CPU < 1%, RAM < 100MB / output в idle.
- Image с hotplug burst (10 подключений/отключений за 30 секунд): no leaks, no crashes.
- Video (если входит): 1080p/30fps CPU path — CPU < 25% на Ryzen 5600 class.

**Экосистемный (смягчён).**
Проект в active maintenance mode ≥ 3 месяцев перед 0.1 релизом: regular commits, responsive issue tracker (median TTFR < 2 недели). Множественность maintainer'ов приветствуется, но не hard gate — требование «2 contributors» было клеткой, не защитой (см. Changelog).

---

## 7. Что 0.1 сознательно **не** обещает

Чтобы не было self-deception:

- **Никакой совместимости с Wallpaper Engine.** Ни одной строчки WE-related кода. Ни импорта, ни preview, ни конверсии.
- **Никаких adapters к внешним программам.** Ни `mpvpaper`, ни `swaybg`, ни `linux-wallpaperengine`.
- **Никакой theming.** Палитру мы не извлекаем, в GTK/Qt не пишем, `wallust` не запускаем.
- **Никаких скриптов.** Lua, Python, JS — нигде в рантайме 0.1.
- **Никакого сетевого взаимодействия.** Ни Steam Workshop, ни weather API, ни RSS, ни удалённых обоев по URL.
- **Никакой multi-user/system-wide конфигурации.** 0.1 — только per-user daemon через systemd user unit.
- **Не кроссплатформа.** Linux + wlroots. FreeBSD — maybe, если работает само; гарантий нет. macOS/Windows — даже не обсуждается.

---

## 8. Как читается этот документ

Если при разработке 0.1 возникает вопрос «добавлять ли фичу X» — **ответ здесь**:

1. Попадает в §2 «что продукт умеет»? → Добавляем.
2. Попадает в §4 «запрещено в Core»? → Не добавляем, никогда.
3. Попадает в §5 «отложено в релиз Y»? → Не в 0.1, ждём Y.
4. Не попадает никуда? → charter-0.1-change PR с обоснованием.

Если ответ на «добавлять ли» не находится за 5 минут в этом документе — charter неполон, и это bug charter'а, а не разработчика.

---

## 9. Phase II gate (превью)

Эта секция — не часть 0.1 scope. Она — **явное обязательство**, что происходит после 1.0. Без неё charter выглядит как «застрянем на 1.x навсегда», что тоже нездорово.

**Release 1.0** = 0.x стабилизирован. IPC frozen. 6 месяцев без critical bugs на full corpus. **Active maintenance mode**: regular releases (минимум security fixes), responsive issue tracker (median TTFR < 2 недели), проект открыт к contributions. Множественность maintainers приветствуется, но формально не требуется — для indie-проекта это cage, а не защита.

**После 1.0 разрешено (и запланировано) Phase II:**
- Adapter SDK.
- Первый adapter: `mpvpaper` (proof of concept).
- Второй adapter: `linux-wallpaperengine` (главная фича 2.0).

**Между 1.0 и 2.0 — максимум 18 месяцев.** Если не успеваем — пересматриваем charter Phase II, не тихо забываем.

Детали Phase II — отдельный `CHARTER-2.0.md`, который пишется после релиза 1.0, не раньше.

---

## 12. Image-only 0.1 — полноценный релиз

Если video не проходит gate §13 — 0.1 релизится **без video**, и это **не провал**.

Explicit rule для release notes и README:
- Формулировки вида «пока без видео, скоро добавим», «beta», «preview» — **запрещены**.
- Правильная формулировка: «0.1 focuses on rock-solid image wallpaper management. Video support — in 0.2.»
- Позиционирование 0.1 — complete product в своём узком классе, не incomplete engine.

Индустриальный precedent: `swaybg`, `wpaperd`, `hyprpaper` релизились и поддерживаются годами **без shader backend**. `swaybg` до сих пор не имеет video. Это не мешает им быть полезными продуктами. Image-only 0.1 — в той же традиции.

---

## 13. Video stretch — date-based cutoff

Video — единственный stretch goal 0.1 (см. §2). Чтобы он не превратился в тихий scope creep, gate зафиксирован **по дате**, не «когда будет готово».

### Правило

К **2026-06-01** video backend должен пройти все три условия:

1. **Функциональная стабильность.** Corpus из 5 тестовых video-файлов (разные codecs: H.264, H.265, VP9, AV1, WebM) проигрывается 30 минут без crash и visual artifacts.
2. **Отсутствие утечек.** `heaptrack`-прогон 60 минут на циклическом переключении между 5 файлами — нулевой net growth памяти (±10MB допустимо как noise).
3. **Performance target.** 1080p/30fps H.264 — CPU ≤ 25% на Ryzen 5600 class.

Если **любое** из трёх условий не выполнено к 2026-06-01 — video **автоматически** переносится в 0.2. Без обсуждения, без «ещё одной недели», без оправданий в release notes.

### Обоснование даты

2026-06-01 — это приблизительно 6 недель после старта implementation по SKELETON.md. Это жёсткая, но реалистичная граница для stretch goal у одного разработчика. Если за 6 недель video не стабилизировался — значит, он не стабилизируется «ещё через неделю», а требует отдельного релиза с полным вниманием (что и делает 0.2).

### Что не является основанием для отмены gate

- «Почти работает».
- «Один edge case остался».
- «Это же stretch, можно же и в 0.1.1 выпустить».
- Эмоциональная привязанность к feature после 6 недель работы.

Gate — механический. Три checkbox'а на 2026-06-01. Нет трёх — нет video в 0.1.

---

## 10. Changelog

- **v1.1 (current)** — applied DIFF-v2.3:
  - GUI вынесен из Core Фазы I навсегда.
  - Shader backend перенесён в 0.2.
  - Video стал stretch goal с date-based cutoff (§13).
  - Добавлен §12: image-only = complete release, без извинений.
  - `ext-idle-notify-v1` и pause-on-idle → 0.2.
  - Phase II gate: maintainer requirement смягчён.
- **v1.0** — первая версия. Написана после четвёртого прохода review цикла, фиксирует узкую рамку 0.1 после дискуссии runtime → native engine → platform → hybrid → **self-sufficient native core**.
