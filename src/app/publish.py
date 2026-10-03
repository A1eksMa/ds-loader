from __future__ import annotations

import json
import posixpath
from typing import Dict, List, Optional

from src.app.context import Context
from src.domain.models import Config, StageReport
from src.domain.publish import (
    build_manifest,
    filter_to_published,
    get_command,
    manifest_entry,
    parse_get_output,
    parse_source_description,
    parse_source_labels,
    source_signature,
    wrap_source_js,
)
from src.domain.result import Err


def publish_stage(ctx: Context) -> StageReport:
    """Перестроить выгрузку для ds-webui: `ds get` -> data/<Source>.js + manifest.js.

    Идемпотентна: отпечаток каждого источника хранится в publish_state_path,
    файл переписывается только при изменении. `manifest.js` — при любом
    изменении набора/содержимого источников (и на самом первом проходе).
    `cfg.force_publish` (CLI: `run --once --force-publish`) отключает эту гейтинг-проверку
    на один тик — полная пересборка без изменения БД.
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
    raw_payloads = parsed.value

    # Сузить каждый источник до показателей с `publish: true` в его `source.json`
    # (см. ds/docs/reference/config-format.md). Источник без файла/без ни одного
    # такого показателя публикует только ключевую колонку — намеренный дефолт
    # («публиковаться должно лишь то, что указано явно»), а не ошибка.
    payloads: Dict[str, dict] = {}
    label_types: Dict[str, Dict[str, str]] = {}
    descriptions: Dict[str, Optional[str]] = {}
    for name, raw_payload in raw_payloads.items():
        raw_source = _read_source_json(ctx, cfg, name)
        labels_cfg = parse_source_labels(raw_source)
        published = {n for n, info in labels_cfg.items() if info.get("publish")}
        payloads[name] = filter_to_published(raw_payload, published)
        label_types[name] = {n: info["type"] for n, info in labels_cfg.items() if n in published}
        descriptions[name] = parse_source_description(raw_source)

    # --force-publish: считать сохранённые отпечатки отсутствующими -> полная пересборка
    # на этот тик, без изменения БД (см. Config.force_publish).
    prev = None if cfg.force_publish else _load_state(ctx, cfg.publish_state_path)
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
        entries = [
            manifest_entry(payloads[n], label_types[n], descriptions[n])
            for n in sorted(payloads)
        ]
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
    if cfg.force_publish:
        lines = ["--force-publish: сохранённые отпечатки проигнорированы"] + lines
    return StageReport("publish", ok=True, changed=len(written), lines=tuple(lines))


# --- source.json (эффектное чтение, разбор — чистые parse_source_labels/
# parse_source_description) ---------------------------------------------------


def _read_source_json(ctx: Context, cfg: Config, name: str) -> bytes:
    path = posixpath.join(cfg.sources_dir, name, "source.json")
    try:
        return ctx.fs.read_bytes(path)
    except OSError:
        return b"{}"


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
