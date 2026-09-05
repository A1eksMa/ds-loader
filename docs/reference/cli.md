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
| `--verbose` | логировать каждый проход в stderr (в режиме цикла). |

Флаги перекрывают значения из `--config`, те — дефолты.

## Вывод и коды возврата

- `--once`: печатает по строке на стадию — `[ingest] ok changed=<N>` и, если есть,
  строки лога с отступом. Код `0`.
- Ошибка конфига (нет `update_dir`, неизвестная стадия, битый файл): `error: <текст>` в
  stderr, код `1`.
- `argparse` не разобрал аргументы: код `2`.
- Режим цикла: не возвращается штатно (Ctrl-C / сигнал).

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
