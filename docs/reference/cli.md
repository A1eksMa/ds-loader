# CLI `ds-loader`

Точка входа — `src/cli/main.py :: main` (`pyproject.toml` → `[project.scripts] ds-loader`).
Только `argparse`, stdlib.

```
ds-loader run [--config PATH] [--once] [--update-dir DIR] [--db PATH]
              [--sources-dir DIR] [--archive-dir DIR] [--interval SECONDS]
              [--ds-pythonpath DIR] [--verbose]
```

Пока одна подкоманда — `run`.

| Аргумент | Значение |
|---|---|
| `--config PATH` | JSON-конфиг (см. [`config.md`](config.md)). Необязателен, если параметры заданы флагами. |
| `--once` | один проход по всем стадиям и выход. Без него — бесконечный цикл с `poll_interval_seconds`. |
| `--update-dir DIR` | директория мониторинга (обязательна, если её нет в конфиге). |
| `--db PATH` | путь к БД `ds`. |
| `--sources-dir DIR` | директория конфигов источников. |
| `--archive-dir DIR` | корень архива. |
| `--interval SECONDS` | интервал опроса (перекрывает `poll_interval_seconds`). |
| `--ds-pythonpath DIR` | `PYTHONPATH` для процесса ядра (перекрывает `ds_pythonpath` из конфига). |
| `--verbose` | подробный лог (уровень `DEBUG`). |
| `--quiet` | только предупреждения и ошибки (`WARNING`+). |

Флаги перекрывают значения из `--config`, те — дефолты.

## Что видно в терминале (режим цикла)

Лог идёт в **stderr**, формат `HH:MM:SS LEVEL сообщение`. Уровень по умолчанию — `INFO`.

- **на старте** — баннер с разрешённой конфигурацией (что смотрим, как зовём ядро, пути,
  интервал, стадии) и подсказка «Ctrl-C — остановить»;
- **тик с активностью** (загрузка / ошибка / новый непонятный файл) — `[ingest] ok · обработано N`
  и по строке на файл: `loaded` / `already-loaded` / `quarantined — <причина>` /
  `skipped-name` / `skipped-unstable`;
- **простой** — раз в ~15 секунд короткая строка `жду данные · проверок N · загружено за сессию M`;
- мусорный / ещё дописываемый файл, лежащий в inbox, упоминается **один раз**, а не каждый тик;
- сбой внутри тика — `WARNING`, цикл продолжается;
- **Ctrl-C** — строка `остановлено · проверок N · загружено за сессию M`, выход с кодом `0`.

Многострочный вывод ядра (например traceback) в строке лога схлопывается в одну; полный текст
— в `<file>.err` рядом с файлом в карантине.

## Вывод и коды возврата

- `--once`: печатает в **stdout** по строке на стадию — `[ingest] ok changed=<N>` и, если есть,
  строки с отступом. Код `0`.
- Ошибка конфига (нет `update_dir`, неизвестная стадия, битый файл): `error: <текст>` в
  stderr, код `1`.
- `argparse` не разобрал аргументы: код `2`.
- Режим цикла: не возвращается штатно (Ctrl-C — код `0`; иной сигнал — по умолчанию ОС).

## Пример

```bash
# разовый проход из cron
ds-loader run --once --update-dir /data/upd --db /data/data.db --sources-dir /data/sources

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
