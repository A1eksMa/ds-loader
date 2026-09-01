from __future__ import annotations

import posixpath
from typing import List

from src.app.context import Context
from src.domain.commands import ledger_key, load_command
from src.domain.models import FileOutcome, SourceFile, StageReport
from src.domain.naming import archive_name, parse_source_file
from src.domain.queue import order_queue
from src.domain.result import Err
from src.domain.timestamps import filename_ts_to_unix

# Статусы FileOutcome
LOADED = "loaded"
ALREADY = "already-loaded"
UNSTABLE = "skipped-unstable"
BAD_NAME = "skipped-name"
QUARANTINED = "quarantined"
ERROR = "error"


def ingest_stage(ctx: Context) -> StageReport:
    """Один проход по директории обновлений: разобрать имена, упорядочить,
    обработать по одному файлу за раз (загрузка -> журнал -> архив)."""
    cfg = ctx.config
    try:
        names = ctx.fs.list_files(cfg.update_dir)
    except OSError as exc:
        return StageReport("ingest", ok=False, changed=0,
                           lines=("директория обновлений недоступна: " + str(exc),))

    queue: List[SourceFile] = []
    lines: List[str] = []
    for name in names:
        parsed = parse_source_file(name)
        if isinstance(parsed, Err):
            lines.append(name + ": " + BAD_NAME + " — " + parsed.error)
            continue
        queue.append(parsed.value)

    outcomes: List[FileOutcome] = []
    loaded = 0
    now = ctx.clock.now()
    for sf in order_queue(queue):
        outcome = _process_one(ctx, sf, now)
        outcomes.append(outcome)
        lines.append(sf.filename + ": " + outcome.status
                     + ((" — " + outcome.detail) if outcome.detail else ""))
        if outcome.status == LOADED:
            loaded += 1

    return StageReport("ingest", ok=True, changed=loaded,
                       lines=tuple(lines), outcomes=tuple(outcomes))


def _process_one(ctx: Context, sf: SourceFile, now: float) -> FileOutcome:
    cfg = ctx.config
    src_path = posixpath.join(cfg.update_dir, sf.filename)

    try:
        content = ctx.fs.read_bytes(src_path)
    except OSError as exc:
        return FileOutcome(sf.filename, sf.source, ERROR, "чтение: " + str(exc))

    key = ledger_key(sf, content)

    # Уже загружали ранее (например, крах между записью журнала и перемещением) —
    # просто доносим файл в архив.
    if ctx.ledger.has(key):
        moved = _move(ctx, src_path, _archive_path(ctx, sf))
        return moved or FileOutcome(sf.filename, sf.source, ALREADY)

    # Файл может ещё дописываться продьюсером.
    try:
        st = ctx.fs.stat(src_path)
    except OSError as exc:
        return FileOutcome(sf.filename, sf.source, ERROR, "stat: " + str(exc))
    if now - st.mtime < cfg.stable_after_seconds:
        return FileOutcome(sf.filename, sf.source, UNSTABLE)

    dt = filename_ts_to_unix(sf.timestamp, cfg.filename_tz)
    if isinstance(dt, Err):
        return _quarantine(ctx, src_path, sf, dt.error)

    result = ctx.ds.run(load_command(cfg, sf, src_path, dt.value))
    if result.exit_code != 0:
        return _quarantine(ctx, src_path, sf, (result.stderr or result.stdout).strip())

    # Журнал — ПЕРЕД перемещением: если крах случится после этого, следующий
    # проход увидит ключ и просто доархивирует файл, не загружая повторно.
    ctx.ledger.record(key, {
        "file": sf.filename,
        "source": sf.source,
        "dt": dt.value,
        "loaded_at": now,
        "stdout": result.stdout.strip(),
    })
    moved = _move(ctx, src_path, _archive_path(ctx, sf))
    if moved is not None:
        return moved
    return FileOutcome(sf.filename, sf.source, LOADED, result.stdout.strip())


# --- вспомогательные (эффектные) ------------------------------------------


def _archive_path(ctx: Context, sf: SourceFile) -> str:
    return posixpath.join(ctx.config.archive_dir, sf.source, archive_name(sf))


def _quarantine_path(ctx: Context, sf: SourceFile) -> str:
    return posixpath.join(ctx.config.quarantine_dir, sf.source, sf.filename)


def _move(ctx: Context, src: str, dst: str):
    """Переместить файл; при ошибке ФС вернуть FileOutcome(ERROR), иначе None."""
    try:
        ctx.fs.move(src, dst)
        return None
    except OSError as exc:
        # имя источника вытащим из пути назначения для отчёта
        return FileOutcome(posixpath.basename(src), "", ERROR, "перемещение: " + str(exc))


def _quarantine(ctx: Context, src_path: str, sf: SourceFile, reason: str) -> FileOutcome:
    dst = _quarantine_path(ctx, sf)
    try:
        ctx.fs.write_text(dst + ".err", reason + "\n")
    except OSError:
        pass
    moved = _move(ctx, src_path, dst)
    if moved is not None:
        return moved
    return FileOutcome(sf.filename, sf.source, QUARANTINED, reason[:200])
