# ds-loader

Оркестратор процесса обновления данных для [`ds`](https://github.com/A1eksMa/ds).

Сейчас реализована одна стадия — **приём**: мониторит директорию, куда источники кладут
выгрузки, и для каждого нового файла вызывает `ds load`, затем архивирует файл. С прицелом
на будущее: сюда же встанут стадии публикации (`ds get` → `data/*.js` + `manifest.js` для
[`ds-webui`](https://github.com/A1eksMa/ds-webui)), управления жизненным циклом и сборки.

С ядром `ds` связан **только через CLI** (argv + код возврата + stdout). Кода ядра не
импортирует.

## Технические требования

Те же, что у `ds`: только стандартная библиотека Python (`>= 3.9`), офлайн, без сетевых
портов, функциональный стиль, чистая архитектура (domain / ports / adapters / app).

## Установка и запуск

```bash
pip install -e .

# один проход (для отладки / cron)
ds-loader run --once --update-dir /data/upd --db /data/data.db

# бесконечный цикл с интервалом опроса из конфига
ds-loader run --config config.json
```

Без установки: `PYTHONPATH=. python3 -m src.cli.main run --once --update-dir ...`.

Параметры берутся из `--config` (JSON, см. [`config.example.json`](config.example.json)),
поверх — флаги CLI. `update_dir` обязателен (в конфиге или через `--update-dir`).

## Что делает приём (стадия `ingest`)

За один проход:

1. читает имена файлов в `update_dir`, разбирает их (`<source>_YYYY-MM-DD_HH-MM-SS_<µs>.json`);
2. упорядочивает: по метке времени (старые → новые), при равенстве — по имени источника;
3. по одному файлу:
   - если файл уже в журнале — просто доносит его в архив (крах-безопасность);
   - если файл ещё дописывается (`mtime` моложе `stable_after_seconds`) — пропуск до следующего прохода;
   - иначе: `ds --db <db> load <sources_dir>/<source> <file> --dt <unix>` (метка из имени, UTC);
   - при успехе — запись в журнал, затем перемещение в `archive/<source>/<source>_YYYY-MM-DD_HH-MM-SS.json`;
   - при ошибке `ds` или битой метке — в `quarantine/<source>/` + `.err`-сайдкар.

`ds` **не идемпотентен**, поэтому «загрузить ровно один раз» держится на журнале
(`ledger_path`, JSONL) с ключом «имя файла + sha256 содержимого». Остаётся крошечное окно
(крах между `commit` в `ds load` и записью журнала) — см.
[`docs/explanation/exactly-once.md`](docs/explanation/exactly-once.md).

## Документация

- [`docs/README.md`](docs/README.md) — карта
- [`docs/explanation/`](docs/explanation/) — зачем, модель стадий, exactly-once
- [`docs/reference/`](docs/reference/) — конфиг, CLI, формат имён, раскладка архива
- [`docs/roadmap/`](docs/roadmap/) — стадии публикации / жизненного цикла / сборки

## Разработка

```bash
./run_tests.sh          # pytest в образе Python 3.9.20
python -m pytest -q     # локально
```

См. [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Лицензия

MIT — см. [`LICENSE`](LICENSE).
