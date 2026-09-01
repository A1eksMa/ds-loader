from __future__ import annotations

import subprocess
from typing import List, Sequence

from src.ports.ds_cli import CommandResult


class SubprocessDsCli:
    """Вызывает ядро `ds` как подпроцесс. `base_cmd` — префикс argv,
    например ["ds"] или ["python", "-m", "src.cli.commands"]."""

    def __init__(self, base_cmd: Sequence[str]) -> None:
        self._base = list(base_cmd)

    def run(self, args: List[str]) -> CommandResult:
        proc = subprocess.run(
            self._base + args,
            capture_output=True,
            text=True,
        )
        return CommandResult(proc.returncode, proc.stdout, proc.stderr)
