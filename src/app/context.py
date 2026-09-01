from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Tuple

from src.domain.models import Config, StageReport
from src.ports.clock import Clock
from src.ports.ds_cli import DsCli
from src.ports.filesystem import FileSystem
from src.ports.ledger import Ledger

# Стадия — чистая по интерфейсу функция: получает контекст, возвращает отчёт.
# Раннер прогоняет список стадий за тик. Сейчас реализована одна — ingest.
Stage = Callable[["Context"], StageReport]


@dataclass(frozen=True)
class Context:
    config: Config
    clock: Clock
    fs: FileSystem
    ds: DsCli
    ledger: Ledger
    stages: Tuple[Stage, ...]
    log: Callable[[str], None]
