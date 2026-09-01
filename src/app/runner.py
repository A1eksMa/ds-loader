from __future__ import annotations

from typing import Callable, Tuple

from src.app.context import Context
from src.domain.models import StageReport

# Реестр стадий. Новые стадии (публикация data/*.js + manifest, жизненный цикл,
# сборка) добавляются сюда и включаются через config.stages.
from src.app.ingest import ingest_stage

STAGES = {
    "ingest": ingest_stage,
}


def run_once(ctx: Context) -> Tuple[StageReport, ...]:
    """Один тик: прогнать все сконфигурированные стадии по порядку."""
    reports = []
    for stage in ctx.stages:
        reports.append(stage(ctx))
    return tuple(reports)


def run_forever(ctx: Context, sleep: Callable[[float], None]) -> None:
    """Бесконечный цикл. `sleep` инъектируется (в тестах — с ограничителем).
    Исключение в тике логируется и не роняет цикл."""
    interval = ctx.config.poll_interval_seconds
    while True:
        try:
            for report in run_once(ctx):
                _log_report(ctx, report)
        except Exception as exc:  # noqa: BLE001 — раннер обязан пережить тик
            ctx.log("тик упал: " + repr(exc))
        sleep(interval)


def _log_report(ctx: Context, report: StageReport) -> None:
    head = "[{stage}] {state} changed={changed}".format(
        stage=report.stage,
        state="ok" if report.ok else "FAIL",
        changed=report.changed,
    )
    ctx.log(head)
    for line in report.lines:
        ctx.log("  " + line)
