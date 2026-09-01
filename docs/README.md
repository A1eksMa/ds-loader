# Документация ds-loader

`ds-loader` — оркестратор процесса обновления данных для [`ds`](https://github.com/A1eksMa/ds).
Связка из трёх проектов:

```
источники → [ ds-loader ] → ds (система записи) → [ ds-loader: публикация ] → ds-webui (просмотр)
             приём                                  (будущая стадия)
```

Сейчас реализована стадия **`ingest`** (приём). Остальное — в [`roadmap/`](roadmap/).

| Раздел | Что внутри |
|---|---|
| [`explanation/overview.md`](explanation/overview.md) | что это, роль в связке, модель стадий |
| [`explanation/stages.md`](explanation/stages.md) | как устроена стадия, как добавить новую |
| [`explanation/exactly-once.md`](explanation/exactly-once.md) | «загрузить ровно один раз»: журнал, крах-безопасность, остаточное окно |
| [`explanation/constraints.md`](explanation/constraints.md) | stdlib-only, Python 3.9, офлайн |
| [`reference/config.md`](reference/config.md) | схема конфига |
| [`reference/cli.md`](reference/cli.md) | команды `ds-loader` |
| [`reference/file-naming.md`](reference/file-naming.md) | формат имён входных файлов |
| [`reference/archive-layout.md`](reference/archive-layout.md) | раскладка `archive/` и `quarantine/` |
| [`roadmap/README.md`](roadmap/README.md) | стадии публикации / жизненного цикла / сборки |
