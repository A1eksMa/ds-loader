from src.domain.result import Err, Ok
from src.domain.timestamps import filename_ts_to_unix


def test_utc_is_deterministic():
    # 2026-08-24 18:08:16 UTC == 1787594896 (calendar.timegm)
    r = filename_ts_to_unix("2026-08-24_18-08-16_552252", tz="utc")
    assert isinstance(r, Ok)
    assert r.value == 1787594896


def test_micros_are_dropped():
    a = filename_ts_to_unix("2026-08-24_18-08-16_000000", tz="utc").value
    b = filename_ts_to_unix("2026-08-24_18-08-16_999999", tz="utc").value
    assert a == b


def test_local_mode_returns_int():
    r = filename_ts_to_unix("2026-08-24_18-08-16_000000", tz="local")
    assert isinstance(r, Ok) and isinstance(r.value, int)


def test_bad_timestamp_is_err():
    assert isinstance(filename_ts_to_unix("nonsense", tz="utc"), Err)
    # 25-й час
    assert isinstance(filename_ts_to_unix("2026-08-24_25-00-00_000000", tz="utc"), Err)


def test_unknown_tz_is_err():
    assert isinstance(filename_ts_to_unix("2026-08-24_18-08-16_000000", tz="mars"), Err)
