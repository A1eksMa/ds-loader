# Changelog

Архивы в этой папке — рабочая версия кода (без тестов и документации), готовая к
распаковке и запуску. Имя архива содержит номер версии: `ds-loader-<version>.tar.gz`.

Для машины без git: скачать один архив вместо файлов по отдельности.

## Распаковка

```bash
mkdir -p /path/to/target/folder
tar -xzf ds-loader-<version>.tar.gz -C /path/to/target/folder
```

Внутри: `src/`, `pyproject.toml`, `LICENSE`, `README.md`, `config.example.json`.

## Запуск

```bash
# если есть pip
pip install -e /path/to/target/folder
ds-loader run --config config.json

# без pip (как на ограниченной машине)
PYTHONPATH=/path/to/target/folder python3 -m src.cli.main run --config config.json
```

`ds-loader` вызывает ядро `ds` подпроцессом. Без pip укажи в `config.json`
`"ds_command": ["python3","-m","src.cli.commands"]` и `"ds_pythonpath": "/path/to/ds"` —
иначе `PYTHONPATH` загрузчика затенит `src` ядра. Полностью — `docs/reference/cli.md` в
репозитории.

---

## 0.5.0a1 — `ds-loader-0.5.0a1.tar.gz`

`ingest` переведён на `ds upload`, `publish` научился фильтровать по `source.json` и
прокидывать `type`, раскладка источника собрана в одну папку, лог стал информативным.

- **`ingest`: `ds load` → `ds upload`** — приём файлов больше не доверяет продьюсеру вслепую:
  `ds upload` отказывает целиком, если в файле новый, необъявленный показатель или значение
  не по объявленному в `source.json` типу (см. `ds/docs/reference/cli.md#ds-upload`). Такой
  файл уходит в `quarantine/`, как и любая другая ошибка `ds`. Никаких изменений в самой
  логике карантина не потребовалось — она уже была общей для любого кода возврата `ds`.
  **Следствие**: у источника должен быть заранее объявлен весь ожидаемый список `labels[]`
  в `source.json` (или он уже должен был грузиться иначе) — иначе первый же файл отклонится.
- **`publish`: фильтр по `source.json`, `type` в `manifest.js`** — публикуется только то, что
  в `source.json` источника явно помечено `"publish": true` (ключевая колонка — всегда).
  Источник без `source.json` или без ни одного такого показателя публикует только ключевую
  колонку — осознанный дефолт («публикуется лишь то, что указано явно»), не ошибка. `type`
  каждого опубликованного показателя прокинут в `manifest.js` новым аддитивным полем
  `label_types` (`{имя: type}`) — существующее поле `labels` (плоский список строк) не
  меняется, контракт `ds-webui` не ломается. Идемпотентность считается уже после фильтра:
  правка `publish`/`type` в `source.json` сама по себе вызывает пересборку.
- **`publish`: `--force-publish`** — принудительная пересборка `data/*.js` + `manifest.js`
  на один тик без изменения БД (сохранённые отпечатки идемпотентности игнорируются). CLI-only
  флаг, не поле `config.json`; осмысленно с `--once`.
- **Раскладка источника собрана в одну папку** — `Config.update_dir`/`archive_dir`/
  `quarantine_dir` убраны (конфиг короче на три поля). Теперь `sources_dir/<source>/` несёт
  всё сразу: `source.json`, `upload/` (мониторит `ingest`, создаётся сама при отсутствии),
  `archive/`, `quarantine/`. Источником считается только поддиректория `sources_dir` с
  `source.json` внутри — то же самое, что уже требуют `ds upload`/`ds get`. Имя файла внутри
  `upload/` не изменилось (`<source>_YYYY-MM-DD_HH-MM-SS_<micros>.json`), но теперь должно
  совпадать с именем папки — иначе файл не трогается, в логе `skipped-misfiled`.
- **Прогресс `ingest` в реальном времени** — вместо тишины до самого конца тика (при большой
  пачке или крупных файлах неотличимо от зависания) лог сразу показывает: сколько файлов к
  обработке, какой файл сейчас начат, когда запущен `ds upload` (самый долгий шаг), и
  результат по готовности. Итоговая сводка по концу тика осталась — это уже краткий пересказ.

**Ломает совместимость** с `0.4.0a1`: конфиг с `update_dir`/`archive_dir`/`quarantine_dir` и
плоской `update_dir`-раскладкой больше не поддерживается — источники нужно разложить по
`sources_dir/<source>/{source.json,upload/}`. `ingest`, ранее работавший через `ds load`,
теперь требует, чтобы `source.json` каждого источника заранее объявлял ожидаемые `labels[]`.

## 0.4.0a1 — `ds-loader-0.4.0a1.tar.gz`

Вторая стадия — **`publish`**: `ds get` → файловый контракт `ds-webui`.

- Новая стадия `publish` (`src/app/publish.py` + `src/domain/publish.py`). За тик:
  `ds get [--preset <webui_preset>]` (stdout, голый JSON) → `<webui_data_dir>/<Source>.js`
  (`window.DS.sources[...] = {meta, data}`) + `<webui_data_dir>/manifest.js`
  (`window.DS_MANIFEST`). Формат — `docs/reference/publish-output.md` и `ds-webui/docs/contract.md`.
- Включается через `"stages": ["ingest", "publish"]`. Новые ключи конфига:
  `webui_data_dir` (обязателен для `publish`), `webui_preset` (пресет для `ds get`,
  по умолчанию — все источники), `publish_state_path` (отпечатки опубликованного,
  по умолчанию `.ds-loader/publish.json`). Флаги: `--webui-data-dir`, `--webui-preset`.
- **Идемпотентно:** отпечаток источника (`gen_max_cnt` + `rows` + показатели) в
  `publish_state_path`; неизменившийся `<Source>.js` не переписывается, `manifest.js` —
  только при изменении набора/содержимого источников или на первом проходе.
- **v1:** `db_max_cnt` в манифесте = `gen_max_cnt` (`ds-loader` — CLI-only, отдельного
  «сырого max по БД» в `ds get` нет). Для живого поллера пресет с `"as_of": null`.
- Сбой `ds get` → `[publish] СБОЙ` в логе, цикл продолжается.
- Контракт с ядром расширен: помимо `ds load` — `ds get [--preset]` → stdout JSON, код `0`.

## 0.3.0a1 — `ds-loader-0.3.0a1.tar.gz`

Информативный лог в терминал для режима цикла (`ds-loader run` без `--once`).

- `logging` в stderr (`HH:MM:SS LEVEL сообщение`), уровень `INFO` по умолчанию;
  `--verbose` → `DEBUG`, `--quiet` → `WARNING`+.
- Баннер на старте с разрешённой конфигурацией (что смотрим, как зовём ядро + `PYTHONPATH`,
  пути, интервал, стадии) и «Ctrl-C — остановить».
- Тик с активностью — `[ingest] ok · обработано N` + строка на каждый файл
  (`loaded` / `already-loaded` / `quarantined — причина` / `skipped-name` / `skipped-unstable`).
- В простое — короткое `жду данные · проверок N · загружено M` раз в ~15 с.
- Мусорный / ещё дописываемый файл в inbox упоминается **один раз**, а не каждый тик.
- Сбой внутри тика — `WARNING`, цикл живёт дальше. `Ctrl-C` — строка `остановлено …`, код `0`
  (раньше был traceback).
- Многострочный вывод ядра в строке лога схлопывается; полный текст — в `<file>.err`.
- `--once` по-прежнему печатает отчёт в stdout.

## 0.2.0a1 (без архива)

- Поле конфига `ds_pythonpath` (и флаг `--ds-pythonpath`): `PYTHONPATH` для процесса ядра,
  **заменяет** унаследованный. Нужно, когда и `ds`, и `ds-loader` запускаются из чекаутов без
  pip как `python -m src.cli.*` — иначе `import src` в процессе ядра находит пакет загрузчика.

## 0.1.0a1 (без архива)

- Первая версия. Одна стадия — `ingest`: мониторинг директории, `ds load` по каждому новому
  файлу `<source>_YYYY-MM-DD_HH-MM-SS_<µs>.json`, архивирование в `archive/<source>/`,
  ошибки — в `quarantine/<source>/` + `.err`.
- Exactly-once: обработка по одному файлу транзакционно + журнал (`ledger_path`, JSONL) с
  ключом `<имя>:sha256(содержимого)`.
- Чистая архитектура (`domain` / `ports` / `adapters` / `app`), только stdlib, Python `>= 3.9`.
- Конфиг — JSON-файл + флаги CLI. Раннер прогоняет упорядоченный список стадий
  (`config.stages`); будущие стадии (`publish`, `lifecycle`, `build`) добавляются в тот же список.
