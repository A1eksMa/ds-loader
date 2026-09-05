from __future__ import annotations

import logging
import time
from typing import Callable, Tuple

from src.app.context import Context
from src.domain.models import StageReport

# Реестр стадий. Новые стадии (публикация data/*.js + manifest, жизненный цикл,
# сборка) добавляются сюда и включаются через config.stages.
from src.app.ingest import ingest_stage

STAGES = {
    "ingest": ingest_stage,
}

_log = logging.getLogger("ds-loader")

# Как часто в простое (нет новых файлов) печатать «я жив».
_HEARTBEAT_SECONDS = 15.0


def run_once(ctx: Context) -> Tuple[StageReport, ...]:
    """Один тик: прогнать все сконфигурированные стадии по порядку."""
    return tuple(stage(ctx) for stage in ctx.stages)


def _banner(ctx: Context) -> None:
    cfg = ctx.config
    ds = " ".join(cfg.ds_command)
    if cfg.ds_pythonpath:
        ds += "  (PYTHONPATH=" + cfg.ds_pythonpath + ")"
    _log.info("ds-loader · старт")
    _log.info("  смотрю:     %s  (каждые %.0f с)", cfg.update_dir, cfg.poll_interval_seconds)
    _log.info("  ядро:       %s", ds)
    _log.info("  БД:         %s", cfg.db_path)
    _log.info("  источники:  %s", cfg.sources_dir)
    _log.info("  архив:      %s", cfg.archive_dir)
    _log.info("  карантин:   %s", cfg.quarantine_dir)
    _log.info("  журнал:     %s", cfg.ledger_path)
    _log.info("  стадии:     %s", ", ".join(cfg.stages))
    _log.info("Ctrl-C — остановить")


# Статусы, которые НЕ меняют состояние файла и потому повторяются тик за тиком
# (файл-мусор лежит в inbox, файл ещё дописывается). Печатаем их один раз.
_RECURRING = frozenset(("skipped-name", "skipped-unstable", "error"))


def _recurring_signature(reports: Tuple[StageReport, ...]) -> frozenset:
    return frozenset(
        (o.filename, o.status)
        for r in reports for o in r.outcomes
        if o.status in _RECURRING
    )


def run_forever(ctx: Context, sleep: Callable[[float], None] = time.sleep) -> None:
    """Бесконечный цикл опроса.

    - на старте печатает баннер с разрешённой конфигурацией;
    - тик с активностью (файлы / ошибки / пропуски) печатается подробно;
    - в простое раз в ~_HEARTBEAT_SECONDS печатает короткую строку «жив»;
    - исключение в тике логируется как WARNING и НЕ роняет цикл;
    - Ctrl-C — чистый выход с итогом.

    `sleep` инъектируется (в тестах — с ограничителем).
    """
    interval = ctx.config.poll_interval_seconds
    heartbeat_every = max(1, int(_HEARTBEAT_SECONDS / interval)) if interval else 1

    _banner(ctx)

    ticks = 0
    loaded = 0
    prev_sig = frozenset()
    try:
        while True:
            ticks += 1
            try:
                reports = run_once(ctx)
            except Exception as exc:  # noqa: BLE001 — раннер обязан пережить тик
                _log.warning("тик #%d упал: %r", ticks, exc)
                sleep(interval)
                continue

            changed = sum(r.changed for r in reports)
            failed = any(not r.ok for r in reports)
            sig = _recurring_signature(reports)
            new_recurring = bool(sig - prev_sig)  # появился новый мусорный/недописанный файл
            prev_sig = sig

            if changed or failed or new_recurring:
                for report in reports:
                    _log_report(report)
                loaded += changed
            elif ticks % heartbeat_every == 0:
                _log.info("жду данные · проверок %d · загружено за сессию %d", ticks, loaded)

            sleep(interval)
    except KeyboardInterrupt:
        _log.info("остановлено · проверок %d · загружено за сессию %d", ticks, loaded)


def _log_report(report: StageReport) -> None:
    level = logging.INFO if report.ok else logging.WARNING
    _log.log(level, "[%s] %s · обработано %d",
             report.stage, "ok" if report.ok else "СБОЙ", report.changed)
    for line in report.lines:
        _log.log(level, "    %s", line)
