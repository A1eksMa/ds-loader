from __future__ import annotations

import hashlib
import posixpath
from typing import List

from src.domain.models import Config, SourceFile


def load_command(cfg: Config, sf: SourceFile, file_path: str, dt: int) -> List[str]:
    """argv для `ds` БЕЗ префикса запуска (его добавляет адаптер DsCli).

    Итог: ds --db <db> load <sources_dir>/<source> <file_path> --dt <dt>
    (`--db` — глобальная опция, идёт до подкоманды `load`).
    """
    source_dir = posixpath.join(cfg.sources_dir, sf.source)
    return ["--db", cfg.db_path, "load", source_dir, file_path, "--dt", str(dt)]


def ledger_key(sf: SourceFile, content: bytes) -> str:
    """Ключ идемпотентности: имя файла + хеш содержимого.

    Хеш ловит повторную укладку того же содержимого даже под другим именем;
    имя в ключе — чтобы ключ был читаемым в журнале.
    """
    digest = hashlib.sha256(content).hexdigest()[:16]
    return sf.filename + ":" + digest
