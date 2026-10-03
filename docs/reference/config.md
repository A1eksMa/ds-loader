# Конфигурация

Источник: `src/config/loader.py`. Порядок: **defaults → файл `--config` (JSON) → флаги CLI**.
Пример — [`../../config.example.json`](../../config.example.json).

```json
{
  "db_path": "data.db",
  "sources_dir": "sources",
  "ledger_path": ".ds-loader/ledger.jsonl",
  "poll_interval_seconds": 5.0,
  "stable_after_seconds": 2.0,
  "filename_tz": "utc",
  "ds_command": ["python3", "-m", "src.cli.commands"],
  "ds_pythonpath": "/opt/ds",
  "stages": ["ingest", "publish"],
  "webui_data_dir": "/opt/ds-webui/data",
  "webui_preset": null,
  "publish_state_path": ".ds-loader/publish.json",
  "publish_cache_path": ".ds-loader/get-cache.json",
  "sources": { "crm": { "prep_cmd": null } }
}
```

| Ключ | Тип | По умолч. | Смысл |
|---|---|---|---|
| `db_path` | string | `data.db` | путь к БД `ds` (передаётся как `ds --db …`). |
| `sources_dir` | string | `sources` | корень источников. `sources_dir/<name>/` несёт всё сразу: `source.json` (конфиг — обязателен, иначе `<name>` не считается источником), `upload/` (мониторит стадия `ingest`, создаётся сама при отсутствии), `archive/`, `quarantine/`. Подробно — [`archive-layout.md`](archive-layout.md). |
| `ledger_path` | string | `.ds-loader/ledger.jsonl` | журнал обработанных (JSONL) — основа exactly-once. Общий на все источники, не внутри `sources_dir`. |
| `poll_interval_seconds` | number > 0 | `5.0` | интервал опроса в режиме цикла. |
| `stable_after_seconds` | number | `2.0` | файл обрабатывается, только если его `mtime` старше этого порога (защита от недописанного файла). |
| `filename_tz` | `"utc"` \| `"local"` | `"utc"` | как трактовать метку времени в имени. `"utc"` — детерминировано; `"local"` — как локальный продьюсер на той же машине. |
| `ds_command` | array<string> | `["ds"]` | префикс argv для вызова ядра. Напр. `["python3","-m","src.cli.commands"]` для чекаута без pip или `["/opt/ds/bin/ds"]`. |
| `ds_pythonpath` | string \| `null` | `null` | `PYTHONPATH` для процесса ядра — **заменяет** унаследованный (остальное окружение наследуется). Нужно, когда и `ds`, и `ds-loader` запускаются из чекаутов без pip как `python -m src.cli.*`: без этого унаследованный `PYTHONPATH` загрузчика заставит `import src` найти пакет загрузчика, а не ядра. `null` → окружение не трогается. |
| `stages` | array<string> | `["ingest"]` | какие стадии гоняет раннер за тик, по порядку. Допустимы `ingest`, `publish`; неизвестная → ошибка конфига. |
| `webui_data_dir` | string \| `null` | `null` | каталог `data/` рядом с `index.html` `ds-webui`, куда стадия `publish` кладёт `<Source>.js` + `manifest.js`. **Обязателен**, если в `stages` есть `publish` (в конфиге или через `--webui-data-dir`). |
| `webui_preset` | string \| `null` | `null` | путь к пресету для `ds get --preset` в стадии `publish`. `null` → все источники, все показатели. Для живого поллера в пресете держи `"query": {"as_of": null}` — тогда `gen_max_cnt` в файле совпадает с текущим максимумом источника. |
| `publish_state_path` | string | `.ds-loader/publish.json` | где стадия `publish` хранит отпечатки уже опубликованных источников — чтобы не переписывать неизменившиеся файлы. Битый/отсутствующий → полная пересборка. |
| `publish_cache_path` | string | `.ds-loader/get-cache.json` | передаётся в каждый вызов `ds get --cache` стадии `publish`. `ds-loader` не хранит своего состояния фолда и ничего в этом файле не интерпретирует — решение «можно ли дотянуть только новые транзакции или нужна полная пересборка» целиком на стороне `ds` (по `struct_version` источника, см. [`ds`'s ADR-0010](https://github.com/A1eksMa/ds/blob/main/docs/decisions/0010-incremental-fold-cache.md)). Итоговый JSON от этого не меняется — только скорость сборки. |
| `sources` | object | `{}` | переопределения на источник. `prep_cmd` — **зарезервировано**, пока не выполняется (см. [`../roadmap/README.md`](../roadmap/README.md)). |

Относительные пути разрешаются от текущей директории; для прода рекомендуются абсолютные.
