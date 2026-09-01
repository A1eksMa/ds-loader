from __future__ import annotations

from typing import Iterable, List

from src.domain.models import SourceFile


def order_queue(files: Iterable[SourceFile]) -> List[SourceFile]:
    """Порядок обработки: сначала по метке времени (старые -> новые), при равенстве —
    по имени источника (алфавит), затем по микросекундам.

    Строка `timestamp` вида `YYYY-MM-DD_HH-MM-SS_ffffff` лексикографически сортируется
    хронологически, поэтому unix-конверсия здесь не нужна.
    """
    return sorted(files, key=lambda sf: (sf.seconds_part, sf.source, sf.micros))
