from __future__ import annotations

import posixpath
from typing import Dict, List, Mapping, Set, Tuple

import pytest

from src.app.context import Context
from src.domain.models import Config
from src.ports.ds_cli import CommandResult
from src.ports.filesystem import FileStat


# --- фейковые адаптеры ------------------------------------------------------


class FakeClock:
    def __init__(self, t: float = 1_000_000.0) -> None:
        self.t = t

    def now(self) -> float:
        return self.t


class FakeFileSystem:
    """Плоское хранилище путь -> (bytes, mtime) + множество существующих директорий."""

    def __init__(self) -> None:
        self.files: Dict[str, Tuple[bytes, float]] = {}
        self.dirs: Set[str] = set()
        self.moves: List[Tuple[str, str]] = []

    def _register_parents(self, path: str) -> None:
        d = posixpath.dirname(path)
        while d:
            self.dirs.add(d)
            parent = posixpath.dirname(d)
            if parent == d:
                break
            d = parent

    def mkdir(self, directory: str) -> None:
        self.dirs.add(directory)

    def add(self, path: str, content: bytes = b"{}", mtime: float = 0.0) -> None:
        self.files[path] = (content, mtime)
        self._register_parents(path)

    def list_files(self, directory: str) -> List[str]:
        if directory not in self.dirs:
            raise FileNotFoundError(directory)
        prefix = directory.rstrip("/") + "/"
        return sorted(
            path[len(prefix):]
            for path in self.files
            if path.startswith(prefix) and "/" not in path[len(prefix):]
        )

    def stat(self, path: str) -> FileStat:
        if path not in self.files:
            raise FileNotFoundError(path)
        content, mtime = self.files[path]
        return FileStat(size=len(content), mtime=mtime)

    def read_bytes(self, path: str) -> bytes:
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path][0]

    def move(self, src: str, dst: str) -> None:
        if src not in self.files:
            raise FileNotFoundError(src)
        self.files[dst] = self.files.pop(src)
        self._register_parents(dst)
        self.moves.append((src, dst))

    def write_text(self, path: str, text: str) -> None:
        self.files[path] = (text.encode("utf-8"), 0.0)
        self._register_parents(path)


class FakeDsCli:
    """Скриптованные ответы. По умолчанию — успех."""

    def __init__(self, result: CommandResult = None) -> None:
        self.result = result or CommandResult(0, "loaded 3 transaction(s)\n", "")
        self.calls: List[List[str]] = []

    def run(self, args):
        self.calls.append(list(args))
        return self.result


class InMemoryLedger:
    def __init__(self) -> None:
        self.entries: Dict[str, Mapping[str, object]] = {}

    def has(self, key: str) -> bool:
        return key in self.entries

    def record(self, key: str, meta) -> None:
        self.entries[key] = dict(meta)


# --- фикстуры ------------------------------------------------------------


@pytest.fixture
def config() -> Config:
    return Config(
        update_dir="upd",
        db_path="data.db",
        sources_dir="sources",
        archive_dir="archive",
        quarantine_dir="quarantine",
        stable_after_seconds=2.0,
        poll_interval_seconds=5.0,
        filename_tz="utc",
    )


@pytest.fixture
def parts(config):
    """Контекст + прямой доступ к фейкам."""
    fs = FakeFileSystem()
    fs.mkdir("upd")
    clock = FakeClock()
    ds = FakeDsCli()
    ledger = InMemoryLedger()

    def make(stages=()):
        return Context(
            config=config, clock=clock, fs=fs, ds=ds, ledger=ledger,
            stages=stages, log=lambda _m: None,
        )

    return {"make": make, "fs": fs, "clock": clock, "ds": ds, "ledger": ledger, "config": config}
