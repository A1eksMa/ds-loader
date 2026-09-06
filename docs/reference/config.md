# Конфигурация

Источник: `src/config/loader.py`. Порядок: **defaults → файл `--config` (JSON) → флаги CLI**.
Пример — [`../../config.example.json`](../../config.example.json).

```json
{
  "update_dir": "/data/upd",
  "db_path": "data.db",
  "sources_dir": "sources",
  "archive_dir": "archive",
  "quarantine_dir": "quarantine",
  "ledger_path": ".ds-loader/ledger.jsonl",
  "poll_interval_seconds": 5.0,
  "stable_after_seconds": 2.0,
  "filename_tz": "utc",
  "ds_command": ["python3", "-m", "src.cli.commands"],
  "ds_pythonpath": "/opt/ds",
  "stages": ["ingest"],
  "sources": { "crm": { "prep_cmd": null } }
}
```

| Ключ | Тип | По умолч. | Смысл |
|---|---|---|---|
| `update_dir` | string | — (**обязателен**) | директория, которую мониторим. Нет дефолта; задаётся в конфиге или `--update-dir`. |
| `db_path` | string | `data.db` | путь к БД `ds` (передаётся как `ds --db …`). |
| `sources_dir` | string | `sources` | директория с поддиректориями-конфигами источников (`sources/<name>/source.json`). |
| `archive_dir` | string | `archive` | корень архива; файлы → `archive/<source>/`. |
| `quarantine_dir` | string | `quarantine` | сюда уходят файлы при ошибке `ds` или битой метке, рядом — `<file>.err`. |
| `ledger_path` | string | `.ds-loader/ledger.jsonl` | журнал обработанных (JSONL) — основа exactly-once. |
| `poll_interval_seconds` | number > 0 | `5.0` | интервал опроса в режиме цикла. |
| `stable_after_seconds` | number | `2.0` | файл обрабатывается, только если его `mtime` старше этого порога (защита от недописанного файла). |
| `filename_tz` | `"utc"` \| `"local"` | `"utc"` | как трактовать метку времени в имени. `"utc"` — детерминировано; `"local"` — как локальный продьюсер на той же машине. |
| `ds_command` | array<string> | `["ds"]` | префикс argv для вызова ядра. Напр. `["python3","-m","src.cli.commands"]` для чекаута без pip или `["/opt/ds/bin/ds"]`. |
| `ds_pythonpath` | string \| `null` | `null` | `PYTHONPATH` для процесса ядра — **заменяет** унаследованный (остальное окружение наследуется). Нужно, когда и `ds`, и `ds-loader` запускаются из чекаутов без pip как `python -m src.cli.*`: без этого унаследованный `PYTHONPATH` загрузчика заставит `import src` найти пакет загрузчика, а не ядра. `null` → окружение не трогается. |
| `stages` | array<string> | `["ingest"]` | какие стадии гоняет раннер за тик. Сейчас допустима только `ingest`; неизвестная → ошибка конфига. |
| `sources` | object | `{}` | переопределения на источник. `prep_cmd` — **зарезервировано**, пока не выполняется (см. [`../roadmap/README.md`](../roadmap/README.md)). |

Относительные пути разрешаются от текущей директории; для прода рекомендуются абсолютные.
