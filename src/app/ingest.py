from __future__ import annotations

import posixpath
from typing import List

from src.app.context import Context
from src.domain.commands import ingest_command, ledger_key
from src.domain.models import Config, FileOutcome, SourceFile, StageReport
from src.domain.naming import archive_name, parse_source_file
from src.domain.queue import order_queue
from src.domain.result import Err
from src.domain.timestamps import filename_ts_to_unix

# Статусы FileOutcome
LOADED = "loaded"
ALREADY = "already-loaded"
UNSTABLE = "skipped-unstable"
BAD_NAME = "skipped-name"
MISFILED = "skipped-misfiled"
QUARANTINED = "quarantined"
ERROR = "error"

# Фиксированные имена поддиректорий внутри sources_dir/<source>/ — не конфигурируются:
# источник и всё, что с ним связано (конфиг + бэкап загруженного), живут в одной папке.
_UPLOAD = "upload"
_ARCHIVE = "archive"
_QUARANTINE = "quarantine"
_SOURCE_CONFIG = "source.json"


def ingest_stage(ctx: Context) -> StageReport:
    """Один проход по всем источникам: для каждого — своя `sources_dir/<source>/upload/`
    (создаётся, если её ещё нет). Разобрать имена, упорядочить по времени, обработать по
    одному файлу за раз (загрузка -> журнал -> архив)."""
    cfg = ctx.config
    try:
        source_names = _discover_sources(ctx, cfg)
    except OSError as exc:
        return StageReport("ingest", ok=False, changed=0,
                           lines=("директория источников недоступна: " + str(exc),))

    queue: List[SourceFile] = []
    lines: List[str] = []
    for source in source_names:
        upload_dir = _upload_dir(cfg, source)
        ctx.fs.mkdir(upload_dir)
        for name in ctx.fs.list_files(upload_dir):
            parsed = parse_source_file(name)
            if isinstance(parsed, Err):
                lines.append(name + ": " + BAD_NAME + " — " + parsed.error)
                continue
            sf = parsed.value
            if sf.source != source:
                lines.append(
                    name + ": " + MISFILED + " — лежит в '" + source
                    + "/upload', а по имени в файле источник '" + sf.source + "'"
                )
                continue
            queue.append(sf)

    ordered = order_queue(queue)
    total = len(ordered)
    if total:
        ctx.log("ingest: к обработке " + str(total) + " файл(ов)")

    outcomes: List[FileOutcome] = []
    loaded = 0
    now = ctx.clock.now()
    for i, sf in enumerate(ordered, start=1):
        progress = "[" + str(i) + "/" + str(total) + "] "
        ctx.log("ingest: " + progress + sf.source + "/" + sf.filename + " — начинаю")
        outcome = _process_one(ctx, sf, now)
        outcomes.append(outcome)
        line = (sf.filename + ": " + outcome.status
                + ((" — " + outcome.detail) if outcome.detail else ""))
        lines.append(line)
        ctx.log("ingest: " + progress + line)
        if outcome.status == LOADED:
            loaded += 1

    return StageReport("ingest", ok=True, changed=loaded,
                       lines=tuple(lines), outcomes=tuple(outcomes))


def _discover_sources(ctx: Context, cfg: Config) -> List[str]:
    """Источники — поддиректории `sources_dir` с `source.json` внутри (это же требует
    `ds upload`/`ds get`). Несуществующая `sources_dir` -> OSError (фатально для тика)."""
    names = ctx.fs.list_dirs(cfg.sources_dir)
    known = []
    for name in names:
        try:
            ctx.fs.read_bytes(posixpath.join(cfg.sources_dir, name, _SOURCE_CONFIG))
        except OSError:
            continue
        known.append(name)
    return sorted(known)


def _process_one(ctx: Context, sf: SourceFile, now: float) -> FileOutcome:
    cfg = ctx.config
    src_path = posixpath.join(_upload_dir(cfg, sf.source), sf.filename)

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

    # Сам вызов может занять заметное время (большой файл — ds его парсит и вставляет
    # построчно) — это единственный по-настоящему «тихий» момент в обработке файла,
    # отсюда лог непосредственно перед стартом подпроцесса.
    ctx.log("ingest: " + sf.source + "/" + sf.filename + " — вызываю ds upload...")
    result = ctx.ds.run(ingest_command(cfg, sf, src_path, dt.value))
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


def _upload_dir(cfg: Config, source: str) -> str:
    return posixpath.join(cfg.sources_dir, source, _UPLOAD)


def _archive_path(ctx: Context, sf: SourceFile) -> str:
    return posixpath.join(ctx.config.sources_dir, sf.source, _ARCHIVE, archive_name(sf))


def _quarantine_path(ctx: Context, sf: SourceFile) -> str:
    return posixpath.join(ctx.config.sources_dir, sf.source, _QUARANTINE, sf.filename)


def _move(ctx: Context, src: str, dst: str):
    """Переместить файл; при ошибке ФС вернуть FileOutcome(ERROR), иначе None."""
    try:
        ctx.fs.move(src, dst)
        return None
    except OSError as exc:
        # имя источника вытащим из пути назначения для отчёта
        return FileOutcome(posixpath.basename(src), "", ERROR, "перемещение: " + str(exc))


def _oneline(text: str, limit: int = 200) -> str:
    """Схлопнуть переносы/отступы в одну строку (для строки лога).
    Полный текст (напр. многострочный traceback ядра) остаётся в .err-сайдкаре."""
    return " ".join(text.split())[:limit]


def _quarantine(ctx: Context, src_path: str, sf: SourceFile, reason: str) -> FileOutcome:
    dst = _quarantine_path(ctx, sf)
    try:
        ctx.fs.write_text(dst + ".err", reason.rstrip() + "\n")
    except OSError:
        pass
    moved = _move(ctx, src_path, dst)
    if moved is not None:
        return moved
    return FileOutcome(sf.filename, sf.source, QUARANTINED, _oneline(reason))
