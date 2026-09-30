from __future__ import annotations

from typing import List, NamedTuple, Protocol


class CommandResult(NamedTuple):
    exit_code: int
    stdout: str
    stderr: str


class DsCli(Protocol):
    """Запуск подкоманды ядра `ds`. Порт общий (не привязан к одной подкоманде) —
    `ingest` вызывает через него `ds upload`, `publish` — `ds get`."""

    def run(self, args: List[str]) -> CommandResult:
        """Ненулевой код возврата — это НЕ исключение (возвращается в CommandResult).
        Отсутствие бинаря `ds` -> FileNotFoundError (фатально, всплывает наверх)."""
        ...
