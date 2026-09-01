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

Единственная реализованная. Алгоритм — [`../reference/`](../reference/) и код
`src/app/ingest.py`. Кратко: разобрать имена → упорядочить → по одному файлу
(журнал → стабильность → `ds load` → журнал → архив / карантин).

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

«Только приём сейчас, расширяемость на будущее» = не хардкодить одну процедуру, а держать
**упорядоченный список стадий**. Публикация для `ds-webui`, архивирование, сборка бандла —
это будущие элементы того же списка, каждый со своим `StageReport`. Раннер, контекст и
конфиг при этом не меняются.
