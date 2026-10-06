from __future__ import annotations

import hashlib
import posixpath
from typing import List

from src.domain.models import Config, SourceFile


def ingest_command(cfg: Config, sf: SourceFile, file_path: str, dt: int, method: str) -> List[str]:
    """argv для `ds` БЕЗ префикса запуска (его добавляет адаптер DsCli).

    Итог: ds --db <db> <method> <sources_dir>/<source> <file_path> --dt <dt>
    (`--db` — глобальная опция, идёт до подкоманды).

    `method` ("upload" | "load") выбирает вызывающая сторона (`src/app/ingest.py`) —
    по умолчанию `upload/`-папка источника зовёт `ds upload` (строгая проверка: новый
    необъявленный показатель или значение не по объявленному в source.json типу —
    отказ, грузится ноль строк, файл уходит в quarantine/ тем же путём, что и любая
    другая ошибка `ds`, см. `src/app/ingest.py::_process_one`). `load/`-папка и
    `watch_dirs` с `method: "load"` в конфиге — сознательно ПРЯМОЙ и МЕНЕЕ БЕЗОПАСНЫЙ
    путь: `ds load` этой проверки не делает (см. README.md «upload vs load»). Выбирать
    `load` стоит только для источников, которым полностью доверяешь.
    """
    source_dir = posixpath.join(cfg.sources_dir, sf.source)
    return ["--db", cfg.db_path, method, source_dir, file_path, "--dt", str(dt)]


def ledger_key(sf: SourceFile, content: bytes) -> str:
    """Ключ идемпотентности: имя файла + хеш содержимого.

    Хеш ловит повторную укладку того же содержимого даже под другим именем;
    имя в ключе — чтобы ключ был читаемым в журнале.
    """
    digest = hashlib.sha256(content).hexdigest()[:16]
    return sf.filename + ":" + digest
