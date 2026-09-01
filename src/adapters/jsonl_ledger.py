from __future__ import annotations

import json
import os
from typing import Mapping, Set


class JsonlLedger:
    """Журнал обработанных файлов — append-only JSONL. Ключи держатся в памяти
    (загружаются при старте), на диск дописываются по одной строке."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._keys: Set[str] = set()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        self._keys.add(json.loads(line)["key"])
                    except (ValueError, KeyError):
                        pass  # битую строку пропускаем, журнал остаётся рабочим

    def has(self, key: str) -> bool:
        return key in self._keys

    def record(self, key: str, meta: Mapping[str, object]) -> None:
        parent = os.path.dirname(self._path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        entry = {"key": key}
        entry.update(meta)
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._keys.add(key)
