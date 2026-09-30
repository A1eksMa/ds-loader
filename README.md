# ds-loader

Оркестратор процесса обновления данных для [`ds`](https://github.com/A1eksMa/ds).

Раннер за тик прогоняет упорядоченный список **стадий** (`config.stages`). Реализованы две:

- **`ingest`** — у каждого источника мониторит его собственную `sources_dir/<source>/upload/`
  (создаёт, если её ещё нет), для каждого нового файла вызывает `ds upload` (строгая загрузка
  — продьюсеру не доверяем вслепую, см. ниже), затем архивирует файл рядом же, в
  `sources_dir/<source>/archive/`;
- **`publish`** — вызывает `ds get` и раскладывает результат как `data/<Source>.js` +
  `data/manifest.js` для [`ds-webui`](https://github.com/A1eksMa/ds-webui) (идемпотентно:
  неизменившиеся файлы не переписываются). Формат — [`docs/reference/publish-output.md`](docs/reference/publish-output.md).

На будущее — стадии жизненного цикла и сборки (см. [`docs/roadmap/`](docs/roadmap/)).

С ядром `ds` связан **только через CLI** (argv + код возврата + stdout). Кода ядра не
импортирует.

## Технические требования

Те же, что у `ds`: только стандартная библиотека Python (`>= 3.9`), офлайн, без сетевых
портов, функциональный стиль, чистая архитектура (domain / ports / adapters / app).

## Установка и запуск

```bash
pip install -e .

# один проход (для отладки / cron)
ds-loader run --once --sources-dir /data/sources --db /data/data.db

# приём + публикация для ds-webui (нужен "stages": ["ingest","publish"] в конфиге)
ds-loader run --once --config config.json

# бесконечный цикл с интервалом опроса из конфига
ds-loader run --config config.json

# принудительно пересобрать выгрузку для ds-webui, не меняя БД
ds-loader run --once --config config.json --force-publish
```

В режиме цикла лог идёт в stderr: баннер с конфигом на старте, подробности по каждому
обработанному файлу, короткий «жду данные …» в простое, `Ctrl-C` — чистый выход с итогом.
`--verbose` — детальнее, `--quiet` — только ошибки. Подробно — [`docs/reference/cli.md`](docs/reference/cli.md).

Без установки: `PYTHONPATH=/opt/ds-loader python3 -m src.cli.main run --once --sources-dir ...`.

Для машины без git — архив кода одним файлом: [`releases/`](releases/) (`ds-loader-<version>.tar.gz`).

Параметры берутся из `--config` (JSON, см. [`config.example.json`](config.example.json)),
поверх — флаги CLI. Всё опционально — `sources_dir` по умолчанию `sources` (относительно
текущей директории).

**Без pip** (оба проекта — чекауты): в конфиге `"ds_command": ["python3","-m","src.cli.commands"]`
и `"ds_pythonpath": "/opt/ds"` — иначе `PYTHONPATH` загрузчика затенит `src` ядра. Подробно —
[`docs/reference/cli.md`](docs/reference/cli.md) → «Запуск без pip».

## Что делает приём (стадия `ingest`)

Всё, что относится к источнику, лежит в одной директории — `sources_dir/<source>/`: его
конфиг (`source.json`) и весь бэкап когда-либо загруженного в него. За один проход:

1. источниками считаются поддиректории `sources_dir`, в которых есть `source.json` (то же,
   что уже требуют `ds upload`/`ds get`); для каждой создаётся (если ещё нет)
   `sources_dir/<source>/upload/`;
2. читает имена файлов в каждой такой `upload/`, разбирает их
   (`<source>_YYYY-MM-DD_HH-MM-SS_<µs>.json` — префикс `<source>` должен совпадать с именем
   папки, иначе `skipped-misfiled`, файл не трогается);
3. упорядочивает по всем источникам разом: по метке времени (старые → новые), при равенстве
   — по имени источника;
4. по одному файлу:
   - если файл уже в журнале — просто доносит его в архив (крах-безопасность);
   - если файл ещё дописывается (`mtime` моложе `stable_after_seconds`) — пропуск до следующего прохода;
   - иначе: `ds --db <db> upload <sources_dir>/<source> <file> --dt <unix>` (метка из имени, UTC);
   - при успехе — запись в журнал, затем перемещение в
     `sources_dir/<source>/archive/<source>_YYYY-MM-DD_HH-MM-SS.json`;
   - при ошибке `ds` или битой метке — в `sources_dir/<source>/quarantine/` + `.err`-сайдкар.

Подробная раскладка — [`docs/reference/archive-layout.md`](docs/reference/archive-layout.md).

**Почему `ds upload`, а не `ds load`**: `ingest` принимает файлы от продьюсеров, а не от
оператора руками — нет гарантии, что конкретный файл действительно от того источника, для
которого его приняли (не говоря уже о банальном дрейфе схемы на стороне продьюсера). `ds
upload` отказывает **целиком** (не грузит ни одной строки), если в файле нашёлся показатель,
которого раньше не было и который не объявлен в `labels[]` его `source.json`, или значение не
парсится под объявленный там тип — такой файл `ingest` уводит в `quarantine/`, как и любую
другую ошибку `ds` (см. [`../ds/docs/reference/cli.md#ds-upload`](https://github.com/A1eksMa/ds/blob/main/docs/reference/cli.md#ds-upload)).
**Следствие**: у источника, планируемого работать через `ingest`, `source.json` должен заранее
объявлять весь ожидаемый список `labels[]` (либо источник уже должен был грузиться хоть раз
иначе — `ds --db ... load ...` вручную) — иначе первый же файл будет отклонён целиком, грузить
попросту не с чем сравнивать.

`ds` **не идемпотентен**, поэтому «загрузить ровно один раз» держится на журнале
(`ledger_path`, JSONL) с ключом «имя файла + sha256 содержимого». Остаётся крошечное окно
(крах между `commit` в `ds upload` и записью журнала) — см.
[`docs/explanation/exactly-once.md`](docs/explanation/exactly-once.md).

## Что делает публикация (стадия `publish`)

Требует `webui_data_dir` (каталог `data/` рядом с `index.html` `ds-webui`). За один проход:

1. `ds get [--preset <webui_preset>]` — свёрнутое состояние источников голым JSON;
2. для каждого источника читается его `sources_dir/<Source>/source.json` и результат
   `ds get` сужается до показателей с `"publish": true` (ключевая колонка остаётся всегда);
   источник без `source.json` или совсем без таких показателей публикует только её —
   это намеренный дефолт (публикуется лишь то, что явно включено), а не ошибка;
3. на каждый источник — `<webui_data_dir>/<Source>.js` (`window.DS.sources[...] = {meta, data}`),
   уже суженный;
4. сборка `<webui_data_dir>/manifest.js` (`window.DS_MANIFEST` — индекс со свежестью), где на
   каждый источник дополнительно кладётся `label_types` — `{имя показателя: type}` из
   `source.json`, для тех же опубликованных показателей (аддитивное поле, `labels` как плоский
   список строк не меняется — контракт `ds-webui`).

Идемпотентно: отпечаток источника (`gen_max_cnt` + опубликованные показатели) хранится в
`publish_state_path`; неизменившийся `<Source>.js` не переписывается — а правка `publish`/`type`
в `source.json` меняет отпечаток и вызывает пересборку, даже если сами данные не менялись.
Формат и ограничение `db_max_cnt = gen_max_cnt` (v1) —
[`docs/reference/publish-output.md`](docs/reference/publish-output.md).

Принудительная пересборка без изменения БД (например, после ручной правки `source.json`,
или просто чтобы убедиться, что выгрузка свежая) — флаг `--force-publish`: на этот тик
сохранённые отпечатки игнорируются, `data/*.js` + `manifest.js` пересобираются целиком.
Осмысленно только с `--once` — в бесконечном цикле форсировал бы пересборку на каждом тике.

## Документация

- [`docs/README.md`](docs/README.md) — карта
- [`docs/explanation/`](docs/explanation/) — зачем, модель стадий, exactly-once
- [`docs/reference/`](docs/reference/) — конфиг, CLI, формат имён, раскладка архива, вывод `publish`
- [`docs/roadmap/`](docs/roadmap/) — жизненный цикл / сборка / честный `db_max_cnt`

## Разработка

```bash
./run_tests.sh          # pytest в образе Python 3.9.20
python -m pytest -q     # локально
```

См. [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Лицензия

MIT — см. [`LICENSE`](LICENSE).
