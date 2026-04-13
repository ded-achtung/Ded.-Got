# Document Diff v2.3 — Final Pruning

Статус: **final before implementation**. Пятый и последний DIFF. Если критика v2.3 потребует v2.4 — останавливаемся, применяем как есть, начинаем код. Пять итераций документов — предел.

**Принцип:** критика v2.2 показала, что cut order — это самозащита, а не честный scope. Проект сам признал перегрев через существование cut order. Лечение — **реально сократить 0.1**, а не откладывать сокращение на «если начнёт гореть».

Этот DIFF supersedes v2.1 и v2.2. Включает все их изменения плюс реальное сокращение.

---

## 1. Что признаём

Честный взгляд на 0.1 из CHARTER-0.1 до v2.2:
- daemon + event loop
- Wayland integration (6 протоколов)
- image backend
- video backend (ffmpeg, CPU path)
- shader backend (GLSL, hot reload)
- multi-output + hotplug + fractional scale
- pause policy (fullscreen + idle)
- profile system v0
- diagnostics system
- IPC + CLI
- GUI (iced)
- config store
- contract infrastructure

**Это не узкое ядро. Это три MVP в одной упаковке.**

Cut order v2.2 признал это косвенно: «если что-то пойдёт не так, вынесем GUI, потом shader, потом video». Но это значит, что проект **уже знает**, что полный scope нереалистичен. Cut order как plan B — честнее, чем без него, но недостаточно честно.

**Финальное решение: режем до того, как начнёт гореть.**

---

## 2. Новый scope 0.1 — одна фраза

**0.1 = stable wlroots wallpaper daemon with IPC, profiles, multi-output, and actionable diagnostics. Image-first. Video — если успеем. Всё остальное — позже.**

### Что это означает конкретно

**Обязательно в 0.1 (не режется):**
1. Daemon + event loop.
2. Wayland integration (layer-shell, xdg-output, fractional-scale, content-type). Foreign-toplevel-list — опционально, для pause-on-fullscreen. `ext-idle-notify-v1` **не в 0.1** — входит в 0.2 вместе с pause-on-idle.
3. Image backend (PNG, JPG, WebP) с per-output fit modes.
4. Multi-output + hotplug.
5. Profile system v0 (Profile + RuntimePolicy, без ActivationRule и Hooks).
6. IPC server + `wpectl` CLI.
7. Diagnostics system с structured warning codes.
8. Config store (TOML).
9. Contract infrastructure (wpe-compat).

**Stretch goal 0.1 (может не войти):**
- Video backend (CPU path). Если к release candidate не стабилен — выносим в 0.2 без drama.

**НЕ в 0.1:**
- ❌ GUI. Выносится навсегда из первой фазы Core. Может стать отдельным проектом (`wpe-gui`) релизом позже. См. §5.
- ❌ Shader backend. Переносится в 0.2 как первая major feature addition после stable image-only release.
- ❌ Pause-on-idle. Требует `ext-idle-notify-v1` integration, которая нетривиальна. Переносится в 0.2.
- ❌ Content-type hints (полный). В 0.1 — только статический hint «photo» для image, без переключения.
- ❌ Всё остальное, что было out-of-scope раньше.

**Итого в 0.1 — 9 обязательных component groups + 1 stretch. Не 13.**

---

## 3. Обоснование каждого сокращения

### 3.1. GUI — вне Core Фазы I навсегда

**Подтверждено fact-checking v2.2:** ни один соседний daemon (swaybg, swww, hyprpaper, wpaperd, mpvpaper) не имеет встроенного GUI. GUI — отдельные проекты (waypaper, hyprwall, awtwall, waytrogen). Это **established pattern**, не compromise.

**Следствие:** GUI в CHARTER-0.1 был не «узким фокусом», а отклонением от mainstream pattern. Возврат к pattern = честность.

**Где живёт GUI после этого:**
- В первой фазе — нигде. Пользователь использует `wpectl` CLI.
- Через 6 месяцев после 0.1 stable — может быть запущен отдельный sub-project `wpe-gui`, если возникнет maintainer capacity.
- Или не запустится никогда, и пользователи будут использовать existing GUIs (waypaper и т.п.) через наш IPC.
- Оба варианта OK.

**Важно:** IPC должен быть достаточно стабильным и документированным, чтобы third-party GUI могли строиться поверх. Это усиливает требование к IPC design, не ослабляет.

### 3.2. Shader backend — в 0.2

**Сложность shader backend была недооценена:**
- GLSL source parsing и compile через `naga` или `wgpu::ShaderModule`.
- Hot reload через inotify.
- Shadertoy uniforms protocol (iTime, iResolution, iMouse, iChannel0..3).
- Texture channel loading.
- Pointer input integration (mouse via wlroots).
- Error reporting на GLSL compile errors.
- Edge cases: bad shaders, infinite loops, GPU hang.

Это **отдельный major feature**, не «ещё один backend». Он заслуживает отдельного релиза, где ему можно уделить внимание.

**Последствия:**
- 0.1 не конкурирует со `wlrs` по shader flexibility. Это OK — wlrs занимает эту нишу.
- 0.2 вводит shader backend как headline feature. Это даёт понятную narrative для релиза.

### 3.3. Video backend — stretch, не обязательно

Video backend с CPU path через ffmpeg — меньше сложности, чем shader, но всё ещё значимая работа:
- ffmpeg-next binding.
- Decode loop в отдельном thread.
- RGBA frame upload в GPU.
- Loop / pause / speed control.
- Codec fallback (не все ffmpeg builds имеют все codecs).

**Компромисс:** видео остаётся как stretch goal для 0.1. Если при подходе к RC видео не стабилизируется — 0.1 релизится как **image-only**, video переносится в 0.2 along with shader.

**Релиз image-only — не провал.** Это значит:
- Image-only wallpaper daemon с profiles + multi-output + diagnostics + stable IPC.
- Конкурирует с `swaybg`/`wpaperd` в своём узком классе.
- Выигрывает за счёт predictability, diagnostics, IPC-first design.

**Explicit statement для release notes:** image-only 0.1 считается полноценным релизом. Release notes и README **не должны оправдываться** за отсутствие video. Формулировки вида «пока без видео, скоро добавим» — запрещены. Правильная формулировка: «0.1 focuses on rock-solid image wallpaper management. Video support — in 0.2.» Позиционирование 0.1 как complete product, не как preview/beta/incomplete.

### 3.4. Pause-on-idle — в 0.2

`ext-idle-notify-v1` integration требует:
- Listen на idle events.
- Restore on activity.
- Battery integration (не paused on idle, если on AC).
- Корректное взаимодействие с pause-on-fullscreen.

Это не «включить одну строчку». В 0.1 — только pause-on-fullscreen (через foreign-toplevel-list, если доступен). Idle — в 0.2.

### 3.5. Maintainer gate — смягчение

**Было (PROJECT.md §1 Phase II gate):** «минимум 2 активных maintainer'а с merge правами».

**Критика v2.2 подтвердила:** для раннего проекта 2 maintainer'а — блокирующее требование. Это не защита, это cage.

**Правка:** заменяем на **«проект имеет активный maintenance mode в течение 6 месяцев»**. Конкретно:
- Merged PR'ы от не-основного автора — желательно, не обязательно.
- Regular release cadence (минимум security fixes).
- Responsive issue tracker (TTFR < 2 недель для нормальных issues).

Это honest bar. 2 maintainers gate — было попыткой имитировать «зрелый проект», не реальная защита.

---

## 4. Конкретные правки к документам

### 4.1. CHARTER-0.1.md — существенный rewrite

**§2 Что продукт 0.1 умеет без адаптеров:**

Было:
> Пять пунктов: image, video, shader, multi-output, CLI + daemon + minimal GUI.

Становится:
```markdown
## 2. Что продукт 0.1 умеет

Исчерпывающий список.

### Must-have (обязательно в 0.1)

1. **Статические изображения** (PNG, JPG, WebP) с режимами fit
   (cover/contain/tile/stretch/center), per-output назначение.
2. **Мультимонитор** с hotplug, включая смешанное HiDPI/стандарт разрешение.
3. **CLI** (`wpectl`) с командами `set`, `list`, `pause`, `resume`, `status`, `ping`.
4. **Profile system** (bundling wallpaper + per-output + basic policy).
5. **Diagnostics system** со structured warning codes и actionable suggestions.

### Stretch (в 0.1 если стабилизируется, иначе в 0.2)

6. **Видео** (MP4, WebM, MKV) через CPU-path декодер ffmpeg.
   Pause-on-fullscreen. Loop, mute/volume.

### НЕ в 0.1

- ❌ Shader backend (GLSL). Переносится в 0.2.
- ❌ GUI. Из первой фазы Core вынесен навсегда. Возможно — отдельный
  sub-project позже.
- ❌ Pause-on-idle. В 0.2.
- ❌ Всё, что ранее было out-of-scope (layered composition, Lua, theme hooks,
  audio-reactive, adapters, WE compat).

Всё. 5 обязательных + 1 stretch.
```

**§3 Core components:**

Удаляются: `Minimal GUI`.
Удаляется: shader backend из Native Backends (остаётся image + video-stretch).
Обновляется: Wayland protocols — убрать idle-notify из обязательных в 0.1.

**§6 Release criteria for 0.1:**

Functional блок переписывается:

```markdown
### Functional (must-have)

- [ ] `wpectl set path/to/image.png` ставит картинку на все подключённые мониторы.
- [ ] `wpectl set path/to/image.png --output DP-1` — per output.
- [ ] `wpectl status` возвращает состояние с диагностикой.
- [ ] Мультимонитор на 3 мониторах смешанного DPI работает стабильно.
- [ ] Hotplug: отключение/подключение без рестарта daemon.
- [ ] Автопауза при fullscreen (если `ext-foreign-toplevel-list-v1` доступен).
- [ ] Restart daemon восстанавливает последнее состояние из `~/.local/state/wpe/`.
- [ ] Profile switch через `wpectl profile switch <name>`.

### Functional (stretch, не блокирует релиз)

- [ ] Video backend: `wpectl set path/to/video.mp4`. Loop, pause, mute.

### Quality, Performance — как было, но без shader-related критериев.
```

**§13 Cut order:**

Упрощается. Теперь cut order нужен только для video:

```markdown
## 13. Cut rule for 0.1

Если video backend не стабилизируется к RC — релизится как **image-only 0.1**.
Video переносится в 0.2 без drama.

Image-only release — это успех, не провал. Продукт всё равно полезен: stable
daemon + multi-output + profiles + diagnostics — уже выигрыш над `swaybg` в
своей нише.

Других cut'ов не предусмотрено. Если что-то из must-have не стабилизируется —
значит релиз не готов, ждём.
```

### 4.2. PROJECT.md — существенный update

**§1 Phase I description:**

Было:
> Image, video, shader, мультимонитор, профили, GUI, диагностика.

Становится:
```
Image (обязательно), video (stretch), мультимонитор, профили, CLI,
диагностика. Shader, GUI, layered composition, Lua, palette, audio-reactive —
в последующих релизах 0.x.
```

**§1 Gate между фазами — смягчить maintainer requirement:**

Было:
> 5. **Минимум 2 активных maintainer'а** с merge правами.

Становится:
```
5. **Проект в активном maintenance mode ≥6 месяцев.** Regular releases
   (минимум bug fixes), responsive issue tracker (median TTFR < 2 недели),
   открытый к contributions (даже если не все приняты).
   Не требуется множественность maintainer'ов формально, но приветствуется.
```

**§4 Tier map:**

Shader переезжает из 0.1 в 0.2:
```
| Tier | Название | Когда |
| A    | Static image | 0.1 (must-have) |
| B    | Video (CPU path) | 0.1 (stretch) or 0.2 |
| B+   | Video HW accel | 0.2 |
| C    | GLSL shader (Shadertoy-style) | 0.2 |
| C+   | WGSL shader | 0.4 |
...
```

**§5 Roadmap:**

**0.1** — Image-first Native Core. Image (must), video (stretch), profiles, CLI, diagnostics, multi-output, hotplug.

**0.2** — Video + Shader + HW Accel + Idle. Добавляет: shader backend, HW video decoding (VA-API), video (если было stretch в 0.1), pause-on-idle, grid-based pause detection.

**0.3** — Palette & Theme Hooks. Как раньше.

**0.4** — Layered Composition + Transitions. Как раньше.

**0.5, 0.6, 0.7-0.9, 1.0** — без изменений.

### 4.3. PLATFORM.md — минимальная правка

**§2 Слой 1 Platform Core:**

Удаляется из списка: `Minimal GUI`.

Добавляется примечание:
```markdown
**GUI не входит в Platform Core.** Это соответствует mainstream pattern экосистемы
(wpaperd, swww, hyprpaper, mpvpaper — ни один не имеет встроенного GUI). GUI
может быть отдельным sub-project `wpe-gui` в будущем, или пользователь может
использовать existing GUIs (waypaper, hyprwall) через наш IPC.

IPC design в 0.1 учитывает возможность third-party GUI frontends. Это усиливает
requirements к IPC stability и documentation.
```

### 4.4. SKELETON.md — минимальная правка

**§2 Состав skeleton:**

Никаких изменений. Skeleton остаётся 4 crate'а (wpe-compat, wpe-backend,
wpe-render-core, wpe-contract-tests).

**§12 После skeleton:**

Обновляется порядок реализации. Последовательность этапов теперь:
```
1. FALLBACK-POLICY.md и DIAGNOSTIC-CODES.md.
2. A0: wpe-daemon + IPC skeleton, wpe-cli + ping.
3. A1: wpe-wayland, wpe-render-wgpu, wpe-backend-image.
4. A2: Profile system v0, diagnostics, multi-output.
5. A3 (stretch): wpe-backend-video.
6. Release 0.1.

GUI (A4 в старом плане) — удалён из плана 0.1.
Shader backend (A3 shader в старом плане) — удалён, переехал в 0.2.
```

---

## 5. Что получаем после сокращения

### 5.1. Честный продукт

0.1 теперь описывается одной фразой без «но» и «если»: **stable wlroots image wallpaper daemon with profiles, IPC, and actionable diagnostics**.

Video — бонус. Shader и GUI — в следующих релизах.

### 5.2. Достижимый scope

Один человек может реально довести это за разумный срок. Не «если повезёт», а **по базовому плану**.

### 5.3. Понятная narrative для каждого релиза

- **0.1:** «stable image wallpaper daemon».
- **0.2:** «adds shader backend, video HW accel, smart pause».
- **0.3:** «adds palette extraction with hooks».
- **0.4:** «adds layered composition».

Каждый релиз — одна headline feature. Это легче продавать (в лучшем смысле — объяснять пользователям) и легче поддерживать.

### 5.4. Конкурентная позиция сохраняется

Ничего не теряем по ключевым competitive dimensions:
- Stability vs hyprpaper — не требует video/shader.
- Multi-output correctness — не требует video/shader.
- Profile system — не требует video/shader.
- Diagnostics — не требует video/shader.

Теряем только «три backend types в первом релизе». Но это было not-a-feature для main persona, это было «wow factor» для нашего эго.

---

## 6. Что НЕ меняем, несмотря на критику

Для полноты — пункты, где я остался при своей позиции:

### 6.1. wlroots-only остаётся

Критик v2.2 согласился: «для 0.x это не слабость». Потолок роста — признан.
Расширение на GNOME/KDE/Cosmic — permanent out of scope.

### 6.2. Rust остаётся

Не обсуждается.

### 6.3. Contract discipline остаётся

`wpe-compat`, `forbidden-imports`, `contract-tests` — ядро подхода.
Это не feature продукта, это method. Сокращение scope не сокращает method.

### 6.4. wgpu остаётся

Не меняем render backend. Один stack, wgpu.

---

## 7. Post-apply checklist

После применения v2.3:

- [ ] CHARTER-0.1 §2 показывает 5 must-have + 1 stretch (не 5 without stretch).
- [ ] CHARTER-0.1 §3 не упоминает `Minimal GUI`.
- [ ] CHARTER-0.1 §13 упрощён: cut rule только про video.
- [ ] CHARTER-0.1 §6 Release criteria разделён на must-have и stretch.
- [ ] PROJECT.md §1 Phase I description — без shader и GUI.
- [ ] PROJECT.md §1 gate #5 — smoothed maintainer requirement.
- [ ] PROJECT.md §4 Tier map — shader в 0.2.
- [ ] PROJECT.md §5 Roadmap — 0.1 image-first, 0.2 adds shader+video+idle.
- [ ] PLATFORM.md §2 — GUI не в Core.
- [ ] SKELETON.md §12 — обновлён порядок реализации.
- [ ] DIFF-v2.1, DIFF-v2.2, DIFF-v2.3 — архивируются как historical record
      итеративного сужения scope.

---

## 8. Пять итераций. Финал

Это пятый и последний DIFF. После его применения документы стабильны. Следующий
ход — код.

История итераций:
- **v1.0** — первая версия project charter.
- **v2.0** — двухфазная модель после critique.
- **DIFF-v2.1** — точечные fact-based правки.
- **DIFF-v2.2** — 4 правки: unified persona, cut order, D7 anti-abstraction,
  Phase II как direction, D10 licensing.
- **DIFF-v2.3 (this)** — реальное сокращение scope 0.1. GUI out, shader в 0.2,
  video как stretch.

Каждая итерация сужала scope и добавляла дисциплины. v2.3 — финал сужения.

**Если возникает искушение v2.4 — правильный ответ: нет. Применяем v2.3 и
начинаем writing skeleton.**

Документы не будут идеальными. Они будут достаточными.

---

## 9. Meta-observation (final)

Этот диалог — упражнение в **сопротивлении собственным идеям через внешнюю
критику**. Каждая итерация документов отвечала на критику, которая указывала
на перегрев или самообман.

v2.3 — последний такт этого упражнения. Мой собственный инстинкт (и инстинкт
автора документа в каждой итерации) был **добавлять**, не убирать. Критика
правильно указывала: **убирать**.

Если код skeleton столкнётся с реальностью и выявит, что даже v2.3 scope
слишком широк — значит, следующий DIFF будет уже не ДО кода, а ПОСЛЕ кода.
Это другой тип DIFF'а: «мы попробовали, не получилось, сокращаем ещё». Он
честнее, потому что опирается на опыт, а не на интуицию.

Но это задача не сейчас. Сейчас — применить v2.3, начать skeleton.

---

## 10. Changelog

- **v2.3 final (current)** — реальное сокращение scope 0.1:
  - GUI → вынос из Core Фазы I навсегда.
  - Shader backend → переезжает в 0.2.
  - Video backend → stretch (может остаться в 0.1, может переехать в 0.2).
  - Pause-on-idle → 0.2.
  - `ext-idle-notify-v1` → вместе с pause-on-idle в 0.2 (не обязательный протокол в 0.1).
  - Image-only 0.1 — explicit complete product, release notes не оправдываются.
  - Maintainer gate → smoothed.
  - Supersedes DIFF-v2.1 и DIFF-v2.2 (их изменения включены).
  - Последний документный DIFF перед началом skeleton implementation.
  - Post-review fixes (v2.3.1 inline): устранено внутреннее противоречие
    по `idle-notify` в §2; добавлен explicit statement для release notes в §3.3.
