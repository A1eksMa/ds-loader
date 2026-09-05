import pytest

from src.app.runner import run_forever, run_once
from src.domain.models import StageReport


def _stage(name, changed=0):
    def s(_ctx):
        return StageReport(name, ok=True, changed=changed)
    return s


def test_run_once_executes_stages_in_order(parts):
    seen = []

    def rec(name):
        def s(_ctx):
            seen.append(name)
            return StageReport(name, ok=True, changed=0)
        return s

    ctx = parts["make"](stages=(rec("a"), rec("b"), rec("c")))
    reports = run_once(ctx)

    assert seen == ["a", "b", "c"]
    assert [r.stage for r in reports] == ["a", "b", "c"]


def test_run_forever_sleeps_between_ticks_and_survives_a_failing_stage(parts):
    ticks = {"n": 0}

    def boom(_ctx):
        raise RuntimeError("kaboom")

    ctx = parts["make"](stages=(boom, _stage("ok")))

    class Stop(Exception):
        pass

    def fake_sleep(seconds):
        assert seconds == parts["config"].poll_interval_seconds
        ticks["n"] += 1
        if ticks["n"] >= 3:
            raise Stop

    with pytest.raises(Stop):
        run_forever(ctx, sleep=fake_sleep)

    assert ticks["n"] == 3  # исключение стадии не уронило цикл


def _ticker(stop_after):
    """fake sleep, поднимает KeyboardInterrupt после N вызовов."""
    n = {"v": 0}

    def sleep(_seconds):
        n["v"] += 1
        if n["v"] >= stop_after:
            raise KeyboardInterrupt

    sleep.count = n
    return sleep


def test_run_forever_banner_and_heartbeat(parts, caplog):
    ctx = parts["make"](stages=(_stage("ingest"),))  # всегда idle (changed=0, без lines)
    with caplog.at_level("INFO", logger="ds-loader"):
        run_forever(ctx, sleep=_ticker(stop_after=4))  # interval=5 -> heartbeat каждые 3 тика
    text = "\n".join(r.message for r in caplog.records)
    assert "ds-loader · старт" in text
    assert "смотрю:" in text and ctx.config.update_dir in text
    assert "жду данные · проверок 3" in text          # 3-й тик = хартбит


def test_run_forever_ctrl_c_summary(parts, caplog):
    ctx = parts["make"](stages=(_stage("ingest", changed=0),))
    with caplog.at_level("INFO", logger="ds-loader"):
        run_forever(ctx, sleep=_ticker(stop_after=2))
    assert any("остановлено · проверок 2" in r.message for r in caplog.records)


def test_run_forever_notable_tick_logs_detail(parts, caplog):
    def stage(_ctx):
        return StageReport("ingest", ok=True, changed=1, lines=("f.json: loaded — loaded 3 transaction(s)",))

    ctx = parts["make"](stages=(stage,))
    with caplog.at_level("INFO", logger="ds-loader"):
        run_forever(ctx, sleep=_ticker(stop_after=1))
    text = "\n".join(r.message for r in caplog.records)
    assert "[ingest] ok · обработано 1" in text
    assert "f.json: loaded" in text
    assert "загружено за сессию 1" in text            # итог по Ctrl-C


def test_run_forever_failing_tick_logs_warning(parts, caplog):
    def boom(_ctx):
        raise RuntimeError("kaboom")

    ctx = parts["make"](stages=(boom,))
    with caplog.at_level("WARNING", logger="ds-loader"):
        run_forever(ctx, sleep=_ticker(stop_after=1))
    assert any(r.levelname == "WARNING" and "упал" in r.message for r in caplog.records)
