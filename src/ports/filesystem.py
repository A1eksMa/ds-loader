from __future__ import annotations

from typing import List, NamedTuple, Protocol


class FileStat(NamedTuple):
    size: int
    mtime: float


class FileSystem(Protocol):
    """Всё обращение к диску идёт через этот порт — в тестах подменяется фейком."""

    def list_files(self, directory: str) -> List[str]:
        """Имена обычных файлов в директории (не пути, не поддиректории).
        Несуществующая директория -> OSError."""
        ...

    def list_dirs(self, directory: str) -> List[str]:
        """Имена непосредственных поддиректорий (не файлов, не рекурсивно).
        Несуществующая директория -> OSError."""
        ...

    def mkdir(self, directory: str) -> None:
        """Создать директорию (и родителей), если её ещё нет. Идемпотентно."""
        ...

    def stat(self, path: str) -> FileStat: ...

    def read_bytes(self, path: str) -> bytes: ...

    def move(self, src: str, dst: str) -> None:
        """Переместить файл, создав родительские директории назначения."""
        ...

    def write_text(self, path: str, text: str) -> None:
        """Записать текстовый файл (для .err-сайдкаров), создав родительские директории."""
        ...
