from __future__ import annotations

import hashlib
import posixpath
from typing import List

from src.domain.models import Config, SourceFile


def ingest_command(cfg: Config, sf: SourceFile, file_path: str, dt: int) -> List[str]:
    """argv для `ds` БЕЗ префикса запуска (его добавляет адаптер DsCli).

    Итог: ds --db <db> upload <sources_dir>/<source> <file_path> --dt <dt>
    (`--db` — глобальная опция, идёт до подкоманды `upload`).

    `ingest` намеренно вызывает `ds upload`, а не `ds load`: приём — это
    файлы от продьюсеров, которым нет полного доверия (см.
    `ds/docs/reference/cli.md#ds-upload`), а не ручная загрузка оператором.
    `upload` отказывает целиком (грузит ноль строк) при новом, необъявленном
    показателе или значении не по объявленному в source.json типу — такой
    файл уйдёт в quarantine/ тем же путём, что и любая другая ошибка `ds`
    (см. src/app/ingest.py::_process_one — код возврата не анализируется,
    любой ненулевой уже уводит файл в карантин).
    """
    source_dir = posixpath.join(cfg.sources_dir, sf.source)
    return ["--db", cfg.db_path, "upload", source_dir, file_path, "--dt", str(dt)]


def ledger_key(sf: SourceFile, content: bytes) -> str:
    """Ключ идемпотентности: имя файла + хеш содержимого.

    Хеш ловит повторную укладку того же содержимого даже под другим именем;
    имя в ключе — чтобы ключ был читаемым в журнале.
    """
    digest = hashlib.sha256(content).hexdigest()[:16]
    return sf.filename + ":" + digest
