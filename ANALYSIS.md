# Полный анализ проекта wpe-rs (deep dive)

Дата: 2026-04-13

---

## 1) TL;DR

Проект уже вышел из состояния «только документы»: в репозитории есть **рабочий skeleton workspace** из 4 crate'ов с формализованными контрактами, инвариантами кадра и recovery-поведением, а также набором contract-тестов (16 тестов, все проходят). Главный технический плюс — строгая граница между backend-логикой и renderer/GPU. Главный риск — на текущем этапе почти всё держится на mock/test-реализациях, а интеграция с реальным Wayland/wgpu runtime остаётся следующим крупным шагом.

---

## 2) Что реально находится в репозитории

### 2.1 Workspace и границы

В корне определён Cargo workspace из 4 пакетов:

- `wpe-compat`
- `wpe-backend`
- `wpe-render-core`
- `wpe-contract-tests`

Prototype исключён из workspace как отдельный throwaway-проект с внешними системными зависимостями.

### 2.2 Объём кода/документации

На момент анализа:

- Markdown: **13 файлов / 4286 строк**
- Rust: **26 файлов / 1741 строка**

Вывод: документация всё ещё объёмнее кода, но разрыв уже не драматический (раньше был почти «доки без кода»).

---

## 3) Архитектурная модель в коде (не только в документах)

### 3.1 Backend contract (`wpe-backend`)

Ключевой trait — `FrameSource` с жизненным циклом:

1. `capabilities()`
2. `prepare(...)`
3. `resize(...)` при изменении поверхности
4. `render_frame(...)` как единая точка выдачи кадра
5. `pause()/resume()` (идемпотентные)
6. `status()`

Это верно отражает Wayland frame-callback модель (не старую `update+produce` пару).

### 3.2 Типы кадров и инварианты

`FrameOutput` задаёт 4 исхода:

- `Cpu { buffer, damage }`
- `DeviceEncoded`
- `Unchanged`
- `SkippedDegraded(reason)`

Плюс формализованы `DamageRegion` и CPU буфер (RGBA8 premultiplied). Это хороший фундамент для deterministic поведения в рантайме.

### 3.3 Renderer contract (`wpe-render-core`)

Renderer отделён от backend и описывает recovery-семантику:

- `SurfaceLost` → локальное восстановление поверхности
- `DeviceLost` → фатал, пересоздание higher-level runtime
- `Transient` → skip текущего кадра

Это снимает типичную «каша из ошибок present path» проблему, характерную для графических приложений.

### 3.4 Compatibility layer (`wpe-compat`)

Слой предназначен для:

- матрицы поддержки
- отчёта о загрузке/деградации
- стандартизованных warning-кодов

Практический плюс — можно строить `wpe diag` как отдельную ценность ещё до feature-rich backend'ов.

---

## 4) Что гарантируют contract-тесты

В `wpe-contract-tests` реализованы сценарии, которые реально защищают от классов багов:

1. **lifecycle_order**: запрет `render_frame` до `prepare`, корректный порядок вызовов
2. **pause_idempotent**: double pause/resume — noop
3. **present_recovery**: различение recoverable/fatal/transient путей
4. **no_gpu_in_backend**: backend остаётся GPU-agnostic
5. **frame_output_invariants**: первый кадр, full damage, статическая неизменность

Факт проверки: `cargo test --workspace` дал **16/16 passed**.

---

## 5) Проверки качества и guardrails

### 5.1 Линт/стиль

- `cargo clippy --workspace --all-targets -- -D warnings` проходит без предупреждений.
- Низкий риск накопления «технического шума» на раннем этапе.

### 5.2 Архитектурная защита от размывания границ

Есть скрипт `tools/forbidden-imports.sh`, который блокирует импорт `wgpu` в:

- `wpe-backend`
- `wpe-render-core`
- `wpe-compat`

Это очень правильная ранняя «рельса», предотвращающая accidental coupling.

### 5.3 Supply-chain baseline

`deny.toml` уже содержит:

- запрет неизвестных registry/git sources
- deny на vulnerability advisories
- allow-list лицензий (без GPL)

Это good baseline, но можно усилить раздел `bans` и policy по минимальным версиям.

---

## 6) Ключевые сильные стороны

1. **Контракт-ориентированный дизайн**: сначала формализованы границы, потом реализации.
2. **Тесты на инварианты, а не только на happy path**.
3. **Разделение ответственности** между backend/render/compat.
4. **Явная деградация и диагностика**, а не «молчаливые fallback'и».
5. **Чистый CI-профиль на текущем skeleton-этапе** (тесты и clippy зелёные).

---

## 7) Риски и «узкие места»

1. **Интеграционный риск**: контракты и mock-тесты хорошие, но ещё не доказана стабильность на реальном Wayland lifecycle при hotplug/resize/stall.
2. **Performance risk**: нет зафиксированных бенчмарков «на железе» по CPU/GPU/memory в условиях нескольких выходов.
3. **Protocol-coverage risk**: scale/viewport/fractional-scale/foreign-toplevel нюансы обычно «ломают» первые релизы.
4. **Документационно-кодовая синхронизация**: часть исторических документов может расходиться с текущим skeleton-кодом.

---

## 8) Что проверить следующим этапом (практический roadmap)

### P0 (сразу)

1. Поднять минимальный runtime с реальным event loop + surface lifecycle + пустой clear color.
2. Добавить интеграционные smoke-тесты (не только contract unit tests) с проверкой жизненного цикла окна/поверхности.
3. Зафиксировать machine-readable telemetry для `wpe diag` (JSON schema).

### P1 (после P0)

4. Ввести perf-baseline:
   - startup latency
   - steady-state CPU для статической картинки
   - memory ceiling
5. Добавить chaos-сценарии:
   - SurfaceLost burst
   - transient present errors
   - rapid output reconfigure

### P2 (перед feature expansion)

6. Ужесточить `cargo-deny` политику на дубликаты и рискованные источники.
7. Добавить ABI/contract regression checks (snapshot тесты публичных типов/ошибок).

---

## 9) Интернет-углубление (что удалось и ограничения)

По запросу выполнена попытка углубить анализ через интернет-источники по экосистеме crate'ов/protocols. Ограничение среды: прямой доступ из shell к registry API (`crates.io`) в этой среде блокировался CONNECT 403, поэтому «онлайн-верификация версий через CLI» недоступна.

Через web-инструмент были попытки найти актуальные источники, но выдача оказалась шумной/нерелевантной для точного version-audit. Поэтому для этого отчёта я **не фиксирую непроверяемые онлайн-утверждения как факты**, чтобы не вносить ложную актуальность.

Рекомендация: для полноценного «интернет-глубокого» слоя в следующем проходе запустить скрипт в среде с доступом к:

- crates.io API
- GitHub Releases (wgpu/smithay/wayland ecosystem)
- freedesktop/gitlab protocol changelogs
- rustsec advisory database

И сохранить результаты в отдельный `ECOSYSTEM-RECON.md` с датированными snapshot-таблицами.

---

## 10) Итоговая оценка

Текущее состояние можно охарактеризовать как **«сильный архитектурный skeleton, готовый к интеграционной фазе»**. Проект качественно подготовлен в части контрактов и дисциплины границ. Чтобы перейти к реальной пользовательской ценности, критично быстро сместить центр тяжести с mock-инвариантов на интеграционные runtime-сценарии (Wayland + renderer + diagnostics на реальной машине).

