from __future__ import annotations

import re

from src.domain.models import SourceFile
from src.domain.result import Err, Ok

# <source>_YYYY-MM-DD_HH-MM-SS_<micros>.json
# source — всё до первого "_"; micros — 1..6 цифр (datetime.strftime("%f") даёт 6).
_PATTERN = re.compile(
    r"^(?P<source>[^_]+)_"
    r"(?P<sec>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})_"
    r"(?P<us>\d{1,6})"
    r"\.json$"
)

_TEMPLATE = "<source>_YYYY-MM-DD_HH-MM-SS_<micros>.json"


def parse_source_file(filename: str) -> "Ok[SourceFile] | Err[str]":
    """Разобрать имя входного файла. Чистая функция, без обращения к ФС."""
    m = _PATTERN.match(filename)
    if m is None:
        return Err("имя не соответствует шаблону " + _TEMPLATE)
    sec = m.group("sec")
    us = m.group("us")
    return Ok(SourceFile(
        filename=filename,
        source=m.group("source"),
        timestamp=sec + "_" + us,
        seconds_part=sec,
        micros=int(us),
    ))


def archive_name(sf: SourceFile) -> str:
    """Имя файла в архиве — без микросекунд."""
    return sf.source + "_" + sf.seconds_part + ".json"
