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
