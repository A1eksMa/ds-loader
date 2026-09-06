from __future__ import annotations

import json
import posixpath
from typing import Dict, List, Optional

from src.app.context import Context
from src.domain.models import StageReport
from src.domain.publish import (
    build_manifest,
    get_command,
    manifest_entry,
    parse_get_output,
    source_signature,
    wrap_source_js,
)
from src.domain.result import Err


def publish_stage(ctx: Context) -> StageReport:
    """Перестроить выгрузку для ds-webui: `ds get` -> data/<Source>.js + manifest.js.

    Идемпотентна: отпечаток каждого источника хранится в publish_state_path,
    файл переписывается только при изменении. `manifest.js` — при любом
    изменении набора/содержимого источников (и на самом первом проходе).
    """
    cfg = ctx.config
    if not cfg.webui_data_dir:
        return StageReport("publish", ok=False, changed=0,
                           lines=("не задан webui_data_dir",))

    res = ctx.ds.run(get_command(cfg))
    if res.exit_code != 0:
        reason = " ".join((res.stderr or res.stdout).split())[:200]
        return StageReport("publish", ok=False, changed=0,
                           lines=("ds get: " + (reason or "код " + str(res.exit_code)),))

    parsed = parse_get_output(res.stdout)
    if isinstance(parsed, Err):
        return StageReport("publish", ok=False, changed=0, lines=(parsed.error,))
    payloads = parsed.value

    prev = _load_state(ctx, cfg.publish_state_path)     # dict | None (нет файла/битый -> None)
    known = prev if prev is not None else {}

    new_sigs: Dict[str, str] = {}
    written: List[str] = []
    for name in sorted(payloads):
        payload = payloads[name]
        sig = source_signature(payload)
        new_sigs[name] = sig
        if known.get(name) == sig:
            continue
        ctx.fs.write_text(
            posixpath.join(cfg.webui_data_dir, name + ".js"),
            wrap_source_js(name, payload),
        )
        written.append(name)

    dropped = sorted(set(known) - set(new_sigs))
    manifest_dirty = bool(written) or bool(dropped) or prev is None
    if manifest_dirty:
        entries = [manifest_entry(payloads[n]) for n in sorted(payloads)]
        ctx.fs.write_text(
            posixpath.join(cfg.webui_data_dir, "manifest.js"),
            build_manifest(entries, ctx.clock.now()),
        )
        _save_state(ctx, cfg.publish_state_path, new_sigs)

    lines = [n + ": пересобран" for n in written]
    lines += [n + ": выбыл из выборки" for n in dropped]
    if manifest_dirty and not written and not dropped:
        lines.append("manifest: обновлён")
    if not manifest_dirty:
        lines.append("без изменений")
    return StageReport("publish", ok=True, changed=len(written), lines=tuple(lines))


# --- состояние (эффектное) ----------------------------------------------------


def _load_state(ctx: Context, path: str) -> Optional[Dict[str, str]]:
    try:
        raw = ctx.fs.read_bytes(path)
    except OSError:
        return None
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    if isinstance(obj, dict) and isinstance(obj.get("sources"), dict):
        return {str(k): str(v) for k, v in obj["sources"].items()}
    return None


def _save_state(ctx: Context, path: str, sigs: Dict[str, str]) -> None:
    ctx.fs.write_text(path, json.dumps({"sources": sigs}, ensure_ascii=False, indent=2) + "\n")
