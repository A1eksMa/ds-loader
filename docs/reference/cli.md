# CLI `ds-loader`

Точка входа — `src/cli/main.py :: main` (`pyproject.toml` → `[project.scripts] ds-loader`).
Только `argparse`, stdlib.

```
ds-loader run [--config PATH] [--once] [--db PATH]
              [--sources-dir DIR] [--interval SECONDS]
              [--ds-pythonpath DIR] [--webui-data-dir DIR] [--webui-preset PATH]
              [--force-publish] [--verbose] [--quiet]
```

Пока одна подкоманда — `run`.

| Аргумент | Значение |
|---|---|
| `--config PATH` | JSON-конфиг (см. [`config.md`](config.md)). Необязателен, если параметры заданы флагами. |
| `--once` | один проход по всем стадиям и выход. Без него — бесконечный цикл с `poll_interval_seconds`. |
| `--db PATH` | путь к БД `ds`. |
| `--sources-dir DIR` | корень источников — `sources_dir/<name>/` несёт `source.json` + `upload/` + `archive/` + `quarantine/` (см. [`config.md`](config.md), [`archive-layout.md`](archive-layout.md)). |
| `--interval SECONDS` | интервал опроса (перекрывает `poll_interval_seconds`). |
| `--ds-pythonpath DIR` | `PYTHONPATH` для процесса ядра (перекрывает `ds_pythonpath` из конфига). |
| `--webui-data-dir DIR` | каталог `data/` для `ds-webui` (стадия `publish`; обязателен, если она в `stages` и не задана в конфиге). |
| `--webui-preset PATH` | пресет для `ds get` в стадии `publish` (перекрывает `webui_preset`). |
| `--force-publish` | стадия `publish` игнорирует сохранённые отпечатки и пересобирает `data/*.js` + `manifest.js` целиком на этот тик, не трогая БД. Не поле `config.json` — только CLI. Осмысленно с `--once`; в бесконечном цикле форсировал бы полную пересборку на каждом тике. |
| `--verbose` | подробный лог (уровень `DEBUG`). |
| `--quiet` | только предупреждения и ошибки (`WARNING`+). |

Флаги перекрывают значения из `--config`, те — дефолты.

## Что видно в терминале (режим цикла)

Лог идёт в **stderr**, формат `HH:MM:SS LEVEL сообщение`. Уровень по умолчанию — `INFO`.

- **на старте** — баннер с разрешённой конфигурацией (корень источников, как зовём ядро,
  пути, интервал, стадии) и подсказка «Ctrl-C — остановить»;
- **тик с активностью** (загрузка / ошибка / новый непонятный файл) — `[ingest] ok · обработано N`
  и по строке на файл: `loaded` / `already-loaded` / `quarantined — <причина>` /
  `skipped-name` / `skipped-misfiled` / `skipped-unstable`;
- **стадия `publish`** (если включена) — `[publish] ok · обработано N` и по строке на источник:
  `<name>: пересобран` / `<name>: выбыл из выборки` / `без изменений`;
  сбой `ds get` → `[publish] СБОЙ` + строка `ds get: <причина>`, цикл продолжается;
- **простой** — раз в ~15 секунд короткая строка `жду данные · проверок N · загружено за сессию M`;
- мусорный / ещё дописываемый файл, лежащий в inbox, упоминается **один раз**, а не каждый тик;
- сбой внутри тика — `WARNING`, цикл продолжается;
- **Ctrl-C** — строка `остановлено · проверок N · загружено за сессию M`, выход с кодом `0`.

Многострочный вывод ядра (например traceback) в строке лога схлопывается в одну; полный текст
— в `<file>.err` рядом с файлом в карантине.

## Вывод и коды возврата

- `--once`: печатает в **stdout** по строке на стадию — `[ingest] ok changed=<N>` и, если есть,
  строки с отступом. Код `0` (даже если стадия сама вернула `ok=False` — например, `sources_dir`
  не существует на диске: это ошибка **стадии**, отработавшей и вернувшей `FAIL`, а не ошибка
  конфига).
- Ошибка конфига (неизвестная стадия, битый файл, `publish` без `webui_data_dir`):
  `error: <текст>` в stderr, код `1`.
- `argparse` не разобрал аргументы: код `2`.
- Режим цикла: не возвращается штатно (Ctrl-C — код `0`; иной сигнал — по умолчанию ОС).

## Пример

```bash
# разовый проход из cron
ds-loader run --once --db /data/data.db --sources-dir /data/sources

# приём + публикация для ds-webui за один проход
ds-loader run --once --db /data/data.db \
  --sources-dir /data/sources --webui-data-dir /opt/ds-webui/data
#   (нужен "stages": ["ingest", "publish"] в конфиге — флага для stages нет)

# демон
ds-loader run --config /etc/ds-loader/config.json --verbose
```

## Запуск без pip (оба проекта — чекауты)

`ds` и `ds-loader` оба используют пакет верхнего уровня `src`, поэтому нельзя просто
положить оба на один `PYTHONPATH`: `import src` найдёт чужой пакет. Схема:

```bash
# загрузчик — со своим PYTHONPATH
PYTHONPATH=/opt/ds-loader python3 -m src.cli.main run --config /etc/ds-loader/config.json
```

а в `config.json` для дочернего процесса ядра:

```json
"ds_command":    ["python3", "-m", "src.cli.commands"],
"ds_pythonpath": "/opt/ds"
```

`ds_pythonpath` **заменяет** унаследованный `PYTHONPATH` только для процесса `ds`, поэтому
его `import src` находит пакет ядра. Если ядро установлено нормально (`pip install .`) и
доступно как команда — достаточно `"ds_command": ["ds"]` без `ds_pythonpath`.
