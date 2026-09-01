from src.domain.naming import archive_name, parse_source_file
from src.domain.result import Err, Ok


def test_parses_canonical_name():
    r = parse_source_file("mashkinas_2026-08-24_18-08-16_552252.json")
    assert isinstance(r, Ok)
    sf = r.value
    assert sf.source == "mashkinas"
    assert sf.seconds_part == "2026-08-24_18-08-16"
    assert sf.micros == 552252
    assert sf.timestamp == "2026-08-24_18-08-16_552252"
    assert sf.filename == "mashkinas_2026-08-24_18-08-16_552252.json"


def test_source_is_everything_before_first_underscore():
    r = parse_source_file("a-b.c_2026-01-02_03-04-05_000001.json")
    assert isinstance(r, Ok)
    assert r.value.source == "a-b.c"


def test_short_micros_ok():
    r = parse_source_file("s_2026-01-02_03-04-05_7.json")
    assert isinstance(r, Ok) and r.value.micros == 7


def test_rejects_wrong_extension():
    assert isinstance(parse_source_file("s_2026-01-02_03-04-05_1.txt"), Err)


def test_rejects_missing_timestamp():
    assert isinstance(parse_source_file("mashkinas.json"), Err)


def test_rejects_no_micros():
    assert isinstance(parse_source_file("s_2026-01-02_03-04-05.json"), Err)


def test_archive_name_drops_micros():
    sf = parse_source_file("mashkinas_2026-08-24_18-08-16_552252.json").value
    assert archive_name(sf) == "mashkinas_2026-08-24_18-08-16.json"
