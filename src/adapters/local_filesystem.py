from __future__ import annotations

import os
import shutil
from typing import List

from src.ports.filesystem import FileStat


class LocalFileSystem:
    """Реальная файловая система (stdlib)."""

    def list_files(self, directory: str) -> List[str]:
        return sorted(e.name for e in os.scandir(directory) if e.is_file())

    def stat(self, path: str) -> FileStat:
        st = os.stat(path)
        return FileStat(size=st.st_size, mtime=st.st_mtime)

    def read_bytes(self, path: str) -> bytes:
        with open(path, "rb") as f:
            return f.read()

    def move(self, src: str, dst: str) -> None:
        parent = os.path.dirname(dst)
        if parent:
            os.makedirs(parent, exist_ok=True)
        shutil.move(src, dst)

    def write_text(self, path: str, text: str) -> None:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
