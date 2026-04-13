# SELF-AUDIT — Honest Gaps

Статус: **honest audit**. Ответ на вопрос «всё ли в порядке в документах на 100%».

**Честный ответ: нет.** Этот документ перечисляет gaps, которые я заметил при глубокой проверке, **без попытки закрыть их все сразу**. Часть из них — реальные баги контрактов, часть — implementation-time concerns, часть — legitimate scope debates.

---

## Предвзятость, которую я признаю

После десяти итераций у меня сформировалась склонность к **завершению**. Каждый новый раз, когда ты спрашиваешь «всё ли в порядке», моя первая реакция — защитить существующие документы. Это плохая позиция для честного audit'а.

Два опасных паттерна моего предыдущего поведения:

1. **Защита «sync-pass завершён»** как substitute для реального анализа. Последние три turn'а я говорил «пакет атомарный» — это было правдой **только** по поводу удаления stale упоминаний shader/idle. Не по поводу правильности контрактов.

2. **Квалификация «implementation-time»** как escape hatch. Когда я не знаю ответа, я переношу вопрос в «implementation будет знать». Это иногда правильно, а иногда способ избежать трудного вопроса сейчас.

Этот self-audit — попытка компенсировать.

---

## Gap 1. Async model документа сломан

**Что в RUNTIME.md §9:**
- `Daemon` — main thread, **tokio runtime**.
- `WaylandConnection` — отдельный thread с `calloop`.
- `Backend::prepare` — **tokio blocking pool**.
- IPC server — **tokio**.

**Реальность экосистемы Smithay (подтверждено web search):**
- `smithay-client-toolkit` построен вокруг `calloop`, не tokio.
- `calloop-wayland-source` интегрирует `wayland-client::EventQueue` как calloop source.
- В реальных проектах (cosmic-desktop plugin) calloop работает на main thread, **tokio на отдельном thread**, mpsc между ними. Это нетривиальная архитектура — её надо спроектировать, а не просто записать «daemon на tokio».

**Последствие:** моя модель в §9 описывает несуществующую архитектуру. Реальный daemon будет либо:
- **calloop-first:** main loop на calloop, wgpu render внутри calloop callbacks, IPC отдельный thread, tokio вообще не нужен (IPC может быть просто unix socket с nonblocking I/O).
- **tokio-first с calloop dispatcher:** tokio::spawn_blocking wraps calloop loop. Работает, но громоздко.

**Severity: HIGH.** Это не implementation detail. Это выбор core-архитектуры, который определит **всё**. Я не делал этот выбор — просто написал «tokio» по привычке к async Rust.

**Действие:** перед skeleton — прототипировать минимальный daemon, который подключается к Wayland через calloop и отвечает на ping через unix socket. Выбрать одну модель. Обновить RUNTIME §9 **по результату прототипа**, не до.

---

## Gap 2. Frame callback model полностью отсутствует

**Что в RUNTIME.md:**
- `FrameSource::update(dt) → produce() → FrameOutput`.
- `Renderer::present(frame)`.

**Реальность Wayland:**
- Client запрашивает frame callback через `wl_surface::frame(callback)`.
- Compositor отправляет `wl_callback::done(time)` когда готов принять следующий кадр.
- Client рисует, attach buffer, damage, commit.
- Если client пытается committ-ить без получения callback — frame может быть skipped.

**Моя модель** предполагает, что Renderer может `present()` в любой момент. Реальный Wayland требует frame callback driven rendering loop — это async by design.

**Severity: HIGH.** Это не implementation detail, это протокольное требование.

**Последствие:** `FrameSource::update/produce` pair неправильный для Wayland. Должен быть:
1. Compositor → frame callback done.
2. Daemon → FrameSource::render_frame(now) -> FrameOutput.
3. Renderer attach + damage + commit.
4. Daemon requests next frame callback.

Это **один** entry point, не два (`update` + `produce`). Статика (image) не требует frame callback на каждый кадр — только при изменениях. Но video и shader требуют.

**Действие:** переделать `FrameSource` trait **после** Gap 1 resolved (прототип daemon). Нельзя зафиксировать frame model без понимания event loop model.

---

## Gap 3. Layer surface initial commit contract не описан

**Wayland requirement (wlr-layer-shell spec):**
> Creating a layer surface from a wl_surface which has a buffer attached or committed is a client error. After creating a layer_surface and setting it up, the client must perform an initial commit **without any buffer attached**. The compositor will reply with configure. The client must acknowledge it and **is then allowed to attach a buffer**.

**Что у меня:**
- RUNTIME.md §10 перечисляет `LayerShell` как протокол.
- `OutputRuntime` lifecycle в §2: «Backend создаётся после Renderer и уничтожается раньше».

**Нигде не зафиксировано:** OutputRuntime должен пройти через three-phase lifecycle:
1. Create layer_surface, set_size/anchor/etc.
2. Empty commit.
3. Wait for configure event.
4. Ack configure.
5. **Now** can attach buffer (Renderer может начать present).

**Severity: MEDIUM.** Implementation-time — компилятор не ловит это, но протокол killтом daemon при нарушении. Нужно в contract-tests, а в моих 5 тестах этого нет.

**Действие:** добавить `ct_layer_surface_lifecycle` test в contract-tests list ПОСЛЕ реализации первого OutputRuntime. Это значит 6 тестов, не 5 — но добавится по факту, не превентивно.

---

## Gap 4. wl_surface double-buffered state не учтён в контракте

**Wayland model:**
- Surface state (buffer, damage, opaque region, input region, scale, viewport) — **double-buffered**.
- Все изменения накапливаются в pending state.
- `wl_surface::commit()` атомарно применяет pending → current.

**Моя модель Renderer::present** предполагает immediate apply. Но на Wayland нужно:
- Attach new buffer.
- Set damage region (для оптимизации — partial damage = compositor перерисует только changed).
- Commit.

Без damage tracking compositor перерисует **весь** output на каждый frame — это performance regression для статики (image не меняется, а compositor всё равно работает).

**Severity: MEDIUM.** Не breaks в 0.1, но съест CPU. CHARTER §6 говорит «статический image: CPU < 1%». Без damage tracking не выполним.

**Действие:** добавить `DamageRegion` в FrameOutput contract. Частично уже есть (`pub damage: DamageRegion`), но реальное использование — implementation-time concern.

**Но есть и честный ответ:** для image backend damage = full region на первый кадр, пустой на последующие. Это выполняется без фундаментальных изменений контракта. Можно оставить implementation detail.

---

## Gap 5. Я не прототипировал ни одну часть

**Факт:** я описал ~2300 строк документации для проекта, в котором написал **ноль строк кода**.

Это включает:
- Trait `FrameSource` с 9 методами, 20+ связанных типов.
- Trait `Renderer` с 5 методами.
- `SupportMatrix`, `LoadReport`, `CompatWarning` система.
- 5 contract tests с mock architecture.
- CI infrastructure с forbidden-imports, clippy rules, deny policy.

**Сколько из этого выдержит первый прототип?** Не знаю. Это честный ответ.

Normal practice для системных проектов — **написать прототип, потом документировать**, не наоборот. Мы пошли другим путём — документация подталкивала критику, критика сужала scope. Это не плохо, но **не заменяет** проверку архитектуры кодом.

**Severity: FOUNDATIONAL.** Это не баг документов, это метабаг процесса.

**Действие:** первый milestone после skeleton — **throwaway prototype daemon** на 200-500 строк, который connects to Wayland, создаёт layer surface, рендерит цветной прямоугольник через wgpu. Это пройдёт через все три Gap'а выше и выявит конкретные несоответствия.

Только **после** этого прототипа — имеет смысл писать `wpe-compat` и делать contract-tests.

Это **изменение порядка** SKELETON §12:
- Было: compat → tests → backend → render → daemon.
- Становится: **prototype daemon → compat → tests → production backend → render**.

Prototype выкидывается после его использования. Его задача — проверить Gap 1-4, не стать основой кода.

---

## Gap 6. Метрики в CHARTER §6 неверифицированы

CHARTER-0.1 §6 обещает:
- 72 часа uptime без утечек.
- CPU < 1% для статики, < 25% для video 1080p/30fps на Ryzen 5600.
- Hotplug 10 подключений/отключений за 30 секунд без crashes.
- IPC round-trip < 10ms.
- Daemon startup < 500ms.

**Откуда эти числа?** Я их придумал как «разумные». Они **могут быть:**
- Слишком слабыми (продукт конкурирует слабее чем хотели).
- Слишком жёсткими (невыполнимы на этом стеке).
- Просто неправильными (72 часа — почему не 168? почему не 24?).

Ни одно из чисел не подтверждено:
- Benchmark'ом аналогичного проекта (wpaperd, swaybg).
- Расчётом сверху (сколько CPU жрёт PNG decode + texture upload).
- Требованием пользователя (что он реально замечает).

**Severity: MEDIUM.** Эти числа станут gate для release. Неправильные числа = либо преждевременный release, либо застревание в 0.1 навсегда.

**Действие:** при prototype daemon (Gap 5) — измерить реальное поведение:
- CPU usage статичного wallpaper.
- Memory footprint.
- Startup time.
- IPC latency.

Обновить CHARTER §6 **по результатам**. Не до.

---

## Gap 7. deny.toml / advisory policy не написан

Я несколько раз упоминал `cargo-deny check` в CI, но никогда не написал сам `deny.toml` с конкретной policy. Это не просто список лицензий.

`cargo-deny` имеет четыре секции:
- `advisories` — security vulnerabilities.
- `licenses` — what's allowed.
- `bans` — disallowed crates/versions.
- `sources` — allowed git/registry sources.

**У меня только `licenses` частично прописан.** Остальное не обсуждалось.

**Severity: LOW.** Implementation-time, но нужен в первый день CI. Иначе первая же security advisory на dependency пройдёт незамеченной.

**Действие:** написать полный `deny.toml` как часть skeleton setup, не до.

---

## Gap 8. Нет ни одной строчки реального wgpu кода в SKELETON

SKELETON §5 описывает `Renderer` trait. Но:
- Ни одного примера как `wgpu::Surface::configure()` вызвать для layer surface.
- Ни одного примера `create_surface` для Wayland.
- `CurrentSurfaceTexture` enum (новый v29 API) упомянут в AUDIT F1, но не в SKELETON.

Прототип Gap 5 закроет это. Без него я не знаю, **работает ли вообще** моя архитектура с wgpu на Wayland.

---

## Что остаётся правильным, несмотря на gaps

Не всё плохо. Эти решения остаются solid даже при полной переработке низкого уровня:

1. **CHARTER-0.1 scope.** Image must + video stretch + GUI out + shader 0.2 — это правильно независимо от async model.
2. **D7 no premature abstractions.** Принцип верный.
3. **wlroots-only focus.** Не меняется.
4. **Профиль = 4 сущности** (Profile / RuntimePolicy / ActivationRule / Hooks). Data model independent от render model.
5. **Diagnostics first-class.** Концепция сохраняется.
6. **Phase II как direction, не обязательство.** Психологически правильно.

**Что потенциально придётся переделать:** RUNTIME §9 (threading), RUNTIME §3 (FrameSource trait), SKELETON contract-tests (mock подразумевает неправильную модель).

**Что точно переделки не требует:** CHARTER, PLATFORM, PROJECT.

---

## Финальный честный вывод

На вопрос «всё ли в порядке в документах на 100%» — **нет**.

Документы на **~70% готовы**:
- Scope — готов.
- Product definition — готов.
- Phase structure — готова.
- Discipline / contracts principles — готовы.

**Не готовы:**
- Async / event loop model — нужен прототип.
- Frame callback integration — нужен прототип.
- Wayland lifecycle в contract-tests — нужен первый real OutputRuntime.
- Performance metrics — нужен measurement.
- Полный deny.toml — нужен при первом CI.

**Меньше всего я уверен в RUNTIME.md §9 (threading) и §3 (FrameSource trait).**

---

## Что делать дальше — честно

**НЕ делать:**
- Ещё один «sync pass» по документам.
- DIFF v2.4.
- Переписывать RUNTIME сейчас, без прототипа.

**Делать:**
1. **Throwaway prototype daemon** (200-500 строк). Задача: connects to Wayland через calloop, создаёт layer surface, рендерит через wgpu цветной прямоугольник, отвечает на ping через unix socket. Никакого wpe-compat, никаких trait'ов, никаких contract-tests. Просто код.
2. **Измерить**: CPU, memory, startup time, IPC latency.
3. **Выбрать**: calloop-first vs tokio+calloop hybrid architecture.
4. **Обновить RUNTIME §9 и §3** по результатам прототипа.
5. **После этого** — начинать настоящий skeleton (wpe-compat с типами).

Это добавляет шаг к плану SKELETON §12, но **убирает** риск построить skeleton на неправильной модели.

---

## Meta

Честный self-audit выявил foundational gaps, которые не ловились итеративной критикой документов. Критика ловит inconsistencies между документами. Audit ловит расхождения между документами и реальностью.

Оба нужны. Но audit **должен включать код**, не только поиск по интернету.

Этот документ — последняя честная итерация документов. Дальше — только код.
