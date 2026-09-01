from __future__ import annotations

from typing import Mapping, Protocol


class Ledger(Protocol):
    """Журнал обработанных файлов — гарантия «загрузить ровно один раз».
    Ядро `ds` не идемпотентно: тот же файл дважды = дубль транзакций."""

    def has(self, key: str) -> bool: ...

    def record(self, key: str, meta: Mapping[str, object]) -> None:
        """Атомарно дописать запись. Вызывается ПЕРЕД перемещением файла в архив."""
        ...
