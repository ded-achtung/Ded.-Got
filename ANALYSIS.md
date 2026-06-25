# Анализ проекта

Дата анализа: **2026-06-25**. Ветка: `claude/project-analysis-530sx4`.

> Этот документ заменяет предыдущий снимок от 2026-04-13 (тот был написан
> *до* реализации скелета и описывал состояние «5 тестов / прототип 391
> строка / неполный `deny.toml`»). Старая версия сохранена в истории git.
> Все факты ниже **проверены запуском** на этой машине (см. §3).

---

## 1. Резюме

Репозиторий содержит **два независимых тела работы**, что важно понять сразу:

1. **wpe-rs** — основной проект. Image-first wallpaper daemon для wlroots-Wayland
   композиторов (Hyprland, Sway, labwc, river, niri, Wayfire) на Rust. Цель —
   заменить разрозненный стек (`swaybg` + `mpvpaper` + скрипты) одним daemon с
   профилями, IPC, честной диагностикой и дисциплинированными контрактами.

2. **ThoughtState pilot** (`q9_pilot/` + `experiments/thoughtstate_pilot_001/`) —
   отдельный Python-эксперимент про retrieval/reasoning-петлю с типизированными
   состояниями. К обоям отношения не имеет; явно помечен как «shadow exploration,
   off-mainline». См. §7.

**Стадия wpe-rs:** прототип + компилируемый скелет. Production-кода нет, но
скелет (4 crate'а, контракты, CI) реализован и **полностью зелёный**.
Throwaway-прототип (505 строк, реальный calloop + layer-shell + wgpu) написан,
но **ни разу не скомпилирован и не запущен на реальном железе** — это
единственный настоящий блокер проекта.

| Метрика | Значение |
|---|---|
| Документация | 13 markdown-файлов, **4286 строк** |
| Rust production-код | 0 строк (только скелет контрактов) |
| Rust скелет | 4 crate'а, ~30 файлов, ~900 строк |
| Прототип (throwaway) | `prototype/src/main.rs`, 505 строк |
| Python-пилот | `q9_pilot/`, ~700 строк + REPORT.md |
| Контрактных тестов (Rust) | 5 файлов / **16 sub-тестов — все проходят** |
| Python-тестов | **28 — все проходят** |

---

## 2. Структура репозитория

```
Ded.-Got/
├── crates/                       # Rust workspace (скелет, реализован)
│   ├── wpe-backend/              #   trait FrameSource + типы кадра/состояния
│   ├── wpe-render-core/          #   trait Renderer + negotiation
│   ├── wpe-compat/               #   SupportMatrix, LoadReport, диагностика
│   └── wpe-contract-tests/       #   моки + 5 контрактных тестов (16 sub)
├── prototype/                    # throwaway: calloop + layer-shell + wgpu (505)
├── q9_pilot/                     # ThoughtState pilot — Python (off-mainline)
├── experiments/
│   └── thoughtstate_pilot_001/   #   REPORT.md по пилоту
├── tools/forbidden-imports.sh    # архитектурный lint (запрет wgpu в backend)
├── .github/workflows/ci.yml      # 4 джобы: build-test, clippy, forbidden, deny
├── deny.toml, clippy.toml        # policy (полные)
└── *.md                          # 13 документов (см. ниже)
```

Документы (по убыванию размера): `SKELETON.md` (644), `RUNTIME.md` (538),
`DIFF-v2.3.md` (455), `DIFF-v2.2.md` (368), `PLATFORM.md` (360), `PROJECT.md`
(281), `SELF-AUDIT.md` (269), `CHARTER-0.1.md` (267), `RECON.md` (266),
`DIFF-v2.1.md` (289), `ANALYSIS.md` (этот), `AUDIT-pre-skeleton.md` (219),
`README.md` (109).

Иерархия источников истины: **CHARTER-0.1 > PROJECT > PLATFORM > RUNTIME >
SKELETON**. Три `DIFF-v2.x` — архив итераций (~1100 строк, только историческая
ценность). Имя репозитория на диске (`Ded.-Got` / GitHub `ded-achtung/ded.-got`)
не связано с именем продукта (`wpe-rs`).

---

## 3. Верификация (что реально запущено)

Toolchain на машине: `cargo 1.94.1`, `rustc 1.94.1` (объявленный MSRV проекта — 1.87).

| Проверка | Команда | Результат |
|---|---|---|
| Сборка + тесты workspace | `cargo test --workspace --all-targets` | ✅ **16 passed, 0 failed** |
| Lint | `cargo clippy --workspace --all-targets -- -D warnings` | ✅ чисто, 0 предупреждений |
| Архитектурная граница | `bash tools/forbidden-imports.sh` | ✅ exit 0 (wgpu не просочился) |
| Python-пилот | `python3 -m unittest test_q9 test_q4_unextended test_q4_extended` | ✅ **28 passed** |

Что **не** проверяемо здесь: `prototype/` исключён из workspace (`exclude`) и
требует системных Wayland/GPU библиотек + живого wlroots-композитора. Его код
не компилировался нигде. Аналогично джоба `deny` в CI требует сети для
advisory DB.

Распределение тестов: все 16 живут в `wpe-contract-tests`; `wpe-backend`,
`wpe-compat`, `wpe-render-core` содержат типы/трейты без собственных тестов (0).

---

## 4. Архитектура wpe-rs (скелет)

Два центральных контракта, разделённых жёсткой границей «backend ничего не
знает о GPU»:

### `FrameSource` (`wpe-backend`) — источник кадров
```
capabilities() · prepare(ctx) · resize(size, scale)
render_frame(req) -> FrameOutput · pause() · resume() · status()
```
- Единый entry point `render_frame`, управляемый frame-callback композитора
  (а не парой `update`+`produce`, как было в ранних документах — это **исправлено**).
- `FrameOutput`: `Cpu{buffer, damage}` / `DeviceEncoded` / `Unchanged` /
  `SkippedDegraded`. Статика возвращает `Unchanged` после первого кадра.
- `pause`/`resume` идемпотентны (есть отдельный контрактный тест).

### `Renderer` (`wpe-render-core`) — презентация
```
surface_format() · surface_size() · negotiate(caps) · present(frame) · status()
```
- Renderer владеет GPU device и surface; backend никогда не трогает GPU напрямую.
- Recovery-контракт: `SurfaceLost` → пересоздать surface один раз; `DeviceLost` →
  фатально, пересоздаёт OutputRuntime; `Transient` → пропустить кадр.

### `wpe-compat` — диагностика как first-class
`SupportMatrix` (PNG/JPEG/WebP = Full), `LoadReport` (`Ok`/`Partial`/`Failed` с
severity), `CompatWarning`, `IgnoredItem`. Это материализация заявленной фичи
«actionable diagnostics».

### Граница D3 (главная инвариантная гарантия)
`wgpu::*` запрещён в `wpe-backend`, `wpe-render-core`, `wpe-compat`. Защита
**тройная**: (1) отсутствие зависимости в Cargo.toml, (2) grep-lint
`forbidden-imports.sh` в CI, (3) контрактный тест `no_gpu_in_backend`. Граница
держится — проверено.

### Контрактные тесты (5 файлов / 16 sub)
`lifecycle_order` (prepare до render; reentrancy-guard; double-prepare паникует),
`pause_idempotent` (4 кейса), `present_recovery` (surface/device lost, transient,
unchanged), `frame_output_invariants` (первый кадр = Cpu+Full damage; второй =
Unchanged), `no_gpu_in_backend`. Стиль — мок `TracedBackend`/`MockRenderer`,
проверка инвариантов через трассировку вызовов и `catch_unwind`.

---

## 5. Продукт и дисциплина scope

Двухфазная модель с явным gate:

- **Фаза I (0.1 → 1.0)** — нативный движок. 0.1 = image must-have (PNG/JPG/WebP,
  fit-modes, мультимонитор, hotplug, fractional scale, профили, IPC по Unix-сокету
  + JSON, CLI `wpe`, `wpe diag`, pause-on-fullscreen). Video — **stretch с
  date-gate**. Далее: shader (0.2), palette/hooks (0.3), layered (0.4), Lua (0.5),
  audio-reactive (0.6).
- **Фаза II (1.x → 2.0)** — adapter к `linux-wallpaperengine`. Собственного WE
  runtime не будет никогда. Time-gate ≥12 мес между фазами.

10 архитектурных решений D1–D10 (Rust; один wgpu-backend; GPU скрыт за
render-core; корпус перед кодом; stop-критерии вместо сроков; web — out
permanently; wlroots-only без premature abstractions; не форкать `wlrs`;
adapter только в Фазе II; лицензия MIT/Apache, GPL запрещён).

**Дисциплина scope — самая сильная сторона проекта.** Механизмы против
scope-creep: date-based cutoff для video, явный список «never in scope»,
boundary-правила B1–B5 (PLATFORM), gate из 6 условий между фазами, требование
charter-change PR для изменений рамки.

---

## 6. Статус 8 gap'ов из SELF-AUDIT

С момента self-audit'а закрыто большинство:

| Gap | Тема | Severity | Статус сейчас |
|---|---|---|---|
| 1 | Async: tokio → calloop | HIGH | ✅ **Решён в дизайне.** calloop-first выбран, RUNTIME §9 переписан (v3.0), прототип реализует. *Не подтверждён запуском.* |
| 2 | Frame callback model | HIGH | ✅ **Решён.** `render_frame` — единый entry point, отражён в трейте и тесте `frame_output_invariants`. |
| 3 | Layer-surface lifecycle | MEDIUM | 🟡 Частично. Прототип делает 3-фазный commit; контрактного теста нет (нужен реальный OutputRuntime). |
| 4 | Double-buffered / damage | MEDIUM | 🟡 Частично. `DamageRegion` в контракте + прототипе; perf на статике не измерен. |
| 5 | Документы до кода | FOUNDATIONAL | 🟡 Смягчён. Скелет + прототип написаны. Но production-кода нет и прототип не запущен. |
| 6 | Perf-метрики не верифицированы | MEDIUM | 🔴 **Открыт.** CPU<1%/video<25% и пр. — нужен реальный прогон. |
| 7 | Неполный `deny.toml` | LOW | ✅ **Решён.** advisories + bans + licenses + sources прописаны. |
| 8 | Нет wgpu-кода на Wayland | LOW | ✅ **Решён** (как артефакт). Прототип содержит реальный `init_wgpu`/render pass. *Не запущен.* |

Все непокрытые пункты (3,4,5,6) сходятся к **одному действию: скомпилировать и
запустить прототип на реальном wlroots-железе и снять метрики.** До этого
момента вся низкоуровневая архитектура остаётся гипотезой, пусть и
правдоподобной.

---

## 7. ThoughtState pilot (Python, off-mainline)

Отдельный исследовательский эксперимент, делящий репозиторий с wpe-rs.

**Что это.** 7-слотовая `ThoughtState` (K — знание, G — цели, Ex — уточнение,
H — гипотезы, E — оценка, T — напряжения, P — предпочтения) с
tension-driven петлёй `think_step`. Полностью детерминированно: regex-экстракторы
+ keyword-overlap retrieval, **без LLM в петле**. Задача — disambiguation
вопросов Q9/Q4 по чанкам из книги «Fluent Python».

**Три эмпирических результата** (из REPORT.md):
1. Q9: основной путь разрешается через P; альтернативный путь без P
   детерминированно «застревает» на конфликте — то есть P необходим.
2. Экстракторы не обобщаются между вопросами; режим отказа — *молчаливо-неверный*
   ответ (уверенный ответ в чужом домене), что хуже, чем stall.
3. P разрешает конфликты **между типами источников, но не внутри типа**: при двух
   претендентах одного `source_type` порядок падает на retrieve-rank
   (keyword-overlap, domain-blind) → возможен уверенный неверный ответ. Вывод:
   проблема на другой оси, чем «сделать P богаче».

**Дисциплина.** Отчёт намеренно не принимает архитектурного решения в той же
сессии, где найдена проблема (Result 3 отложен), и явно перечисляет, чего пилот
**не** показал. Это методологически зрелый артефакт.

**Замечание для проекта.** Технически к wallpaper-движку это не относится — это
работа про reasoning/retrieval-состояния агентов. Соседство в одном репо
организационно странно и может путать контрибьюторов wpe-rs. Стоит либо явно
описать в README, что репозиторий мультипроектный, либо вынести пилот в
отдельный репозиторий/`experiments/`-only с собственным README.

---

## 8. Риски

- **🔴 Невалидированная архитектура (главный риск).** Всё низкоуровневое
  (calloop-first, frame-callback, layer lifecycle, wgpu-on-Wayland, метрики)
  держится на прототипе, который ни разу не запускался. Первый прогон на реальном
  железе может потребовать переработки трейтов.
- **🟡 Unsafe-хак в прототипе.** `Surface<'static>` через `mem::transmute`
  (`init_wgpu`) — заявлен к замене на `Arc<WlSurface>`, но это место, где легко
  получить UB при невнимательной миграции.
- **🟡 Indie/один мейнтейнер.** Gate Фазы II допускает single-maintainer; темп
  и bus-factor — реальные риски для проекта такого объёма амбиций.
- **🟡 Конкурентное поле.** `swww`/`hyprpaper`/`swaybg`/`mpvpaper`/`wlrs` уже
  существуют. Дифференциация (единый daemon + профили + диагностика + контракты)
  разумна, но целиком зависит от исполнения.
- **🟢 MSRV не закреплён.** Объявлен 1.87, но нет `rust-toolchain.toml`; CI берёт
  `stable` (здесь 1.94). Низкий риск, но MSRV де-факто не проверяется.

---

## 9. Мелкие несоответствия в документах

Большинство расхождений из апрельского анализа **исправлены** (RUNTIME v3.0
снял PROTOTYPE-PENDING; SKELETON теперь корректно говорит «5 contract-tests
(16 sub-tests)»; `deny.toml` полон). Осталось:

1. `SKELETON.md` §13 (≈стр. 571) всё ещё описывает контрактные тесты как
   пустые заглушки, которые «падают — это ожидаемое состояние». Сейчас они
   реализованы и проходят (16/16) — строка устарела.
2. Имя репозитория (`ded.-got`) не отражает содержимое (`wpe-rs` + ThoughtState).
3. README описывает только wpe-rs и не упоминает, что репозиторий мультипроектный.

---

## 10. Рекомендации

**Критический путь (блокирует всё):**
1. **Скомпилировать и запустить `prototype/` на реальном wlroots-композиторе.**
   Это снимает gap'ы 3–6 одним действием. До этого — не писать production-код.
2. Снять реальные метрики (CPU статики, RAM, startup, IPC latency) и обновить
   CHARTER §6 по фактам, а не по «разумным» догадкам.
3. Заменить `mem::transmute`-хак на `Arc<WlSurface>` при переносе кода прототипа.

**Дальше:**
4. Собрать `corpus-A` (seed: 10 файлов) параллельно с первым backend'ом.
5. Реализовать `wpe diag` как первый запускаемый бинарь (до image-backend).
6. Добавить контрактный тест layer-surface lifecycle при первом OutputRuntime.

**Гигиена репозитория:**
7. Обновить устаревшую строку в `SKELETON.md` §13 (тесты проходят, не падают).
8. Решить судьбу ThoughtState: задокументировать мультипроектность в README
   либо вынести пилот отдельно.
9. Рассмотреть `rust-toolchain.toml` для закрепления MSRV.

**Чего не делать** (повторяя вывод самого проекта): ещё один проход по
документам / DIFF v2.4; переписывать RUNTIME без запуска прототипа; добавлять
фичи в scope 0.1.

---

## 11. Итоговая оценка

Зрелый по **дисциплине и инженерной гигиене**, незрелый по **проверенному
коду**. Скелет чистый, контракты продуманы, граница «no-GPU-in-backend»
реально защищена тремя механизмами, CI зелёный по всем 4 джобам, scope защищён
лучше, чем в 90% indie-проектов. SELF-AUDIT честен и большинство его gap'ов
закрыто.

Единственное, что отделяет проект от «настоящего старта», — **один запуск
прототипа на реальном железе**. Вся архитектура корректна *на бумаге и в
скелете*; её соответствие реальному Wayland пока не доказано. Это осознанный,
явно зафиксированный риск, а не упущение.

ThoughtState-пилот — качественный, но посторонний для wpe-rs артефакт; его
соседство стоит прояснить организационно.
