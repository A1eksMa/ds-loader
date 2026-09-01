# CLI `ds-loader`

Точка входа — `src/cli/main.py :: main` (`pyproject.toml` → `[project.scripts] ds-loader`).
Только `argparse`, stdlib.

```
ds-loader run [--config PATH] [--once] [--update-dir DIR] [--db PATH]
              [--sources-dir DIR] [--archive-dir DIR] [--interval SECONDS] [--verbose]
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

Без установки пакета: `PYTHONPATH=. python3 -m src.cli.main run --once --update-dir …`.

> `ds` и `ds-loader` оба используют пакет верхнего уровня `src`, поэтому их нельзя
> `pip install -e` в **одно** окружение. В проде — раздельные venv (или `ds` установлен
> глобально), а `ds_command` в конфиге указывает на рабочий способ вызвать ядро
> (`["ds"]`, `["/opt/ds/venv/bin/ds"]`, `["/usr/bin/env","-u","PYTHONPATH","ds"]` при
> запуске из чекаута и т.п.).
