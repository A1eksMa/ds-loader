from __future__ import annotations

import argparse
import logging
import sys
import time
from typing import Optional

from src.adapters.jsonl_ledger import JsonlLedger
from src.adapters.local_filesystem import LocalFileSystem
from src.adapters.subprocess_ds_cli import SubprocessDsCli
from src.adapters.system_clock import SystemClock
from src.app.context import Context
from src.app.runner import STAGES, run_forever, run_once
from src.config.loader import load_config
from src.domain.models import Config
from src.domain.result import Err


def _setup_logging(verbose: bool, quiet: bool) -> None:
    level = logging.DEBUG if verbose else (logging.WARNING if quiet else logging.INFO)
    logging.basicConfig(
        stream=sys.stderr,
        level=level,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )


def _build_context(cfg: Config) -> Context:
    return Context(
        config=cfg,
        clock=SystemClock(),
        fs=LocalFileSystem(),
        ds=SubprocessDsCli(cfg.ds_command, cfg.ds_pythonpath),
        ledger=JsonlLedger(cfg.ledger_path),
        stages=tuple(STAGES[name] for name in cfg.stages),
        log=logging.getLogger("ds-loader").info,
    )


def _print_reports(reports) -> None:
    for r in reports:
        print("[{0}] {1} changed={2}".format(r.stage, "ok" if r.ok else "FAIL", r.changed))
        for line in r.lines:
            print("  " + line)


def _run(args: argparse.Namespace) -> int:
    _setup_logging(args.verbose, args.quiet)

    overrides = {
        "update_dir": args.update_dir,
        "db_path": args.db,
        "sources_dir": args.sources_dir,
        "archive_dir": args.archive_dir,
        "poll_interval_seconds": args.interval,
        "ds_pythonpath": args.ds_pythonpath,
        "webui_data_dir": args.webui_data_dir,
        "webui_preset": args.webui_preset,
    }
    cfg_r = load_config(args.config, overrides)
    if isinstance(cfg_r, Err):
        print("error: " + cfg_r.error, file=sys.stderr)
        return 1

    ctx = _build_context(cfg_r.value)

    if args.once:
        _print_reports(run_once(ctx))
        return 0

    run_forever(ctx, sleep=time.sleep)
    return 0


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="ds-loader", description="ds ingest orchestrator")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="run the ingest loop (or one pass with --once)")
    run_p.add_argument("--config", help="path to config JSON")
    run_p.add_argument("--once", action="store_true", help="single pass, then exit")
    run_p.add_argument("--update-dir", help="directory to watch (required if not in config)")
    run_p.add_argument("--db", help="ds database path")
    run_p.add_argument("--sources-dir", help="directory with per-source config dirs")
    run_p.add_argument("--archive-dir", help="archive root")
    run_p.add_argument("--interval", type=float, help="poll interval, seconds")
    run_p.add_argument("--ds-pythonpath",
                       help="PYTHONPATH for the ds subprocess (replaces the inherited one)")
    run_p.add_argument("--webui-data-dir",
                       help="каталог data/ для ds-webui (обязателен для стадии publish)")
    run_p.add_argument("--webui-preset",
                       help="пресет для `ds get` в стадии publish (по умолчанию — все источники)")
    run_p.add_argument("--verbose", action="store_true", help="подробный лог (DEBUG)")
    run_p.add_argument("--quiet", action="store_true", help="только предупреждения и ошибки")

    args = parser.parse_args(argv)
    if args.command == "run":
        return _run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
