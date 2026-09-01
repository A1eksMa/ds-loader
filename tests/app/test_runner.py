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
