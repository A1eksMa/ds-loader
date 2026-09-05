from __future__ import annotations

import os
import subprocess
from typing import List, Optional, Sequence

from src.ports.ds_cli import CommandResult


class SubprocessDsCli:
    """Вызывает ядро `ds` как подпроцесс.

    `base_cmd` — префикс argv, например ["ds"] или ["python3", "-m", "src.cli.commands"].
    `pythonpath` — если задан, у дочернего процесса PYTHONPATH ЗАМЕНЯЕТСЯ на это
    значение (остальное окружение наследуется). Нужно, когда ядро запускается
    как `python -m src.cli.commands` из чекаута без pip: иначе унаследованный от
    загрузчика PYTHONPATH заставит `import src` найти пакет загрузчика, а не ядра.
    """

    def __init__(self, base_cmd: Sequence[str], pythonpath: Optional[str] = None) -> None:
        self._base = list(base_cmd)
        self._pythonpath = pythonpath

    def run(self, args: List[str]) -> CommandResult:
        env = None
        if self._pythonpath is not None:
            env = os.environ.copy()
            env["PYTHONPATH"] = self._pythonpath

        proc = subprocess.run(
            self._base + args,
            capture_output=True,
            text=True,
            env=env,
        )
        return CommandResult(proc.returncode, proc.stdout, proc.stderr)
