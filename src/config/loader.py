from __future__ import annotations

import json
from typing import Any, Mapping, Optional

from src.domain.models import Config, SourceConfig
from src.domain.result import Err, Ok

_KNOWN_STAGES = {"ingest"}
_KNOWN_TZ = {"utc", "local"}


def load_config(
    path: Optional[str],
    overrides: Optional[Mapping[str, Any]] = None,
) -> "Ok[Config] | Err[str]":
    """defaults <- файл (JSON) <- overrides (CLI). Затем валидация."""
    data: dict = {}

    if path is not None:
        try:
            raw = json.loads(open(path, "r", encoding="utf-8").read())
        except (OSError, ValueError) as exc:
            return Err("не прочитан конфиг " + path + ": " + str(exc))
        if not isinstance(raw, dict):
            return Err("конфиг должен быть JSON-объектом")
        data.update(raw)

    for key, value in (overrides or {}).items():
        if value is not None:
            data[key] = value

    if not data.get("update_dir"):
        return Err("не задан update_dir (в конфиге или через --update-dir)")

    tz = data.get("filename_tz", "utc")
    if tz not in _KNOWN_TZ:
        return Err("filename_tz должен быть одним из " + str(sorted(_KNOWN_TZ)))

    try:
        interval = float(data.get("poll_interval_seconds", 5.0))
        stable = float(data.get("stable_after_seconds", 2.0))
    except (TypeError, ValueError):
        return Err("poll_interval_seconds / stable_after_seconds должны быть числами")
    if interval <= 0:
        return Err("poll_interval_seconds должен быть > 0")

    stages = tuple(data.get("stages", ("ingest",)))
    unknown = [s for s in stages if s not in _KNOWN_STAGES]
    if unknown:
        return Err("неизвестные стадии: " + ", ".join(unknown))

    ds_command = tuple(data.get("ds_command", ("ds",)))
    if not ds_command:
        return Err("ds_command не может быть пустым")

    ds_pythonpath = data.get("ds_pythonpath")
    if ds_pythonpath is not None:
        ds_pythonpath = str(ds_pythonpath)

    sources_raw = data.get("sources", {}) or {}
    sources = {}
    for name, spec in sources_raw.items():
        spec = spec or {}
        prep = spec.get("prep_cmd")
        sources[name] = SourceConfig(prep_cmd=tuple(prep) if prep else None)

    return Ok(Config(
        update_dir=str(data["update_dir"]),
        db_path=str(data.get("db_path", "data.db")),
        sources_dir=str(data.get("sources_dir", "sources")),
        archive_dir=str(data.get("archive_dir", "archive")),
        quarantine_dir=str(data.get("quarantine_dir", "quarantine")),
        ledger_path=str(data.get("ledger_path", ".ds-loader/ledger.jsonl")),
        poll_interval_seconds=interval,
        stable_after_seconds=stable,
        filename_tz=tz,
        ds_command=ds_command,
        ds_pythonpath=ds_pythonpath,
        stages=stages,
        sources=sources,
    ))
