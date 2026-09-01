from __future__ import annotations

import calendar
from datetime import datetime

from src.domain.result import Err, Ok

_FMT = "%Y-%m-%d_%H-%M-%S_%f"


def filename_ts_to_unix(timestamp: str, tz: str = "utc") -> "Ok[int] | Err[str]":
    """Метка времени из имени файла -> unix-время в секундах (микросекунды отбрасываются).

    `tz` определяет, как трактовать наивную метку:
      - "utc"   -> calendar.timegm (детерминировано, не зависит от TZ машины);
      - "local" -> datetime.timestamp() (совместимо с продьюсером на той же машине).
    Ядро `ds` ожидает бизнес-время в `--dt`, поэтому по умолчанию — явный UTC.
    """
    try:
        dt = datetime.strptime(timestamp, _FMT)
    except ValueError as exc:
        return Err("невалидная метка времени: " + str(exc))

    if tz == "utc":
        return Ok(calendar.timegm(dt.timetuple()))
    if tz == "local":
        return Ok(int(dt.timestamp()))
    return Err("неизвестный filename_tz: " + tz)
