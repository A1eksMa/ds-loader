from src.domain.naming import parse_source_file
from src.domain.queue import order_queue


def _sf(name):
    return parse_source_file(name).value


def test_orders_by_timestamp_then_source():
    files = [
        _sf("beta_2026-01-01_00-00-05_000000.json"),
        _sf("alpha_2026-01-01_00-00-05_000000.json"),
        _sf("zzz_2026-01-01_00-00-01_000000.json"),
    ]
    names = [sf.source for sf in order_queue(files)]
    assert names == ["zzz", "alpha", "beta"]  # раньше по времени; при равенстве — алфавит


def test_micros_break_final_tie():
    files = [
        _sf("s_2026-01-01_00-00-01_000500.json"),
        _sf("s_2026-01-01_00-00-01_000100.json"),
    ]
    assert [sf.micros for sf in order_queue(files)] == [100, 500]


def test_string_timestamp_sorts_chronologically_across_boundaries():
    files = [
        _sf("s_2026-02-01_00-00-00_000000.json"),
        _sf("s_2026-01-31_23-59-59_000000.json"),
        _sf("s_2025-12-31_00-00-00_000000.json"),
    ]
    got = [sf.seconds_part for sf in order_queue(files)]
    assert got == ["2025-12-31_00-00-00", "2026-01-31_23-59-59", "2026-02-01_00-00-00"]
