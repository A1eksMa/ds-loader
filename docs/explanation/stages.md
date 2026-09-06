# Модель стадий

## Что такое стадия

```python
Stage = Callable[[Context], StageReport]
```

`Context` (`src/app/context.py`) несёт конфиг и порты (`clock`, `fs`, `ds`, `ledger`).
`StageReport` (`src/domain/models.py`) — единый конверт результата: `stage`, `ok`, `changed`
(единиц работы), `lines` (лог), `outcomes` (детально, заполняет `ingest`).

Раннер (`run_once`) вызывает стадии по порядку из `ctx.stages`; `run_forever` крутит это в
цикле с интервалом и не падает от исключения внутри стадии.

## Стадия `ingest`

Приём. Алгоритм — [`../reference/`](../reference/) и код `src/app/ingest.py`. Кратко:
разобрать имена → упорядочить → по одному файлу (журнал → стабильность → `ds load` →
журнал → архив / карантин).

## Стадия `publish`

Перестройка выгрузки для `ds-webui`. Код — `src/app/publish.py` (эффекты) +
`src/domain/publish.py` (чистое). Формат вывода — [`../reference/publish-output.md`](../reference/publish-output.md).

За тик: `ds get [--preset webui_preset]` (вывод — stdout, голый JSON) → на каждый источник
`<webui_data_dir>/<Source>.js` (`window.DS.sources[...] = {meta, data}`) → сборка
`<webui_data_dir>/manifest.js` (`window.DS_MANIFEST` с per-source свежестью).

- Требует `webui_data_dir` (иначе — ошибка конфига).
- **Идемпотентна:** отпечаток источника (`gen_max_cnt` + `rows` + показатели) хранится в
  `publish_state_path`; неизменившийся `<Source>.js` не переписывается, `manifest.js` — только
  при изменении набора/содержимого источников или на первом проходе.
- **v1:** `db_max_cnt` в манифесте = `gen_max_cnt` (`ds-loader` — CLI-only, отдельного
  «сырого max по БД» в `ds get` нет). Подробно и про судьбу выбывших файлов —
  [`../reference/publish-output.md`](../reference/publish-output.md).
- Сбой `ds get` → `StageReport(ok=False)`, раннер логирует `WARNING`, цикл живёт дальше.

## Как добавить стадию

1. `src/app/<name>.py`:
   ```python
   def <name>_stage(ctx: Context) -> StageReport:
       ...
       return StageReport("<name>", ok=True, changed=n, lines=(...))
   ```
   Всё внешнее — только через `ctx.fs` / `ctx.ds` / `ctx.ledger` / `ctx.clock`.
   Нужен новый вид эффекта → новый порт в `src/ports/` + адаптер + фейк в `conftest`.

2. Зарегистрировать:
   - `src/app/runner.py :: STAGES["<name>"] = <name>_stage`
   - `src/config/loader.py :: _KNOWN_STAGES.add("<name>")`

3. Включается через конфиг: `"stages": ["ingest", "<name>"]`.

4. Тесты в `tests/app/test_<name>.py` на фейках; сложную чистую логику вынести в
   `src/domain/` и покрыть в `tests/domain/`.

## Почему так

«Оркестратор, а не одна процедура» = не хардкодить шаги, а держать **упорядоченный список
стадий**. `ingest` и `publish` — первые два элемента; архивирование (`lifecycle`), сборка
бандла (`build`) — будущие элементы того же списка, каждый со своим `StageReport`. Раннер и
контекст при добавлении стадии не меняются.
