from src.domain.commands import ledger_key, load_command
from src.domain.models import Config
from src.domain.naming import parse_source_file


def _cfg(**kw):
    base = dict(update_dir="upd", db_path="data.db", sources_dir="sources")
    base.update(kw)
    return Config(**base)


def _sf(name="mashkinas_2026-08-24_18-08-16_552252.json"):
    return parse_source_file(name).value


def test_load_command_shape():
    cmd = load_command(_cfg(), _sf(), "upd/mashkinas_2026-08-24_18-08-16_552252.json", 1787594896)
    assert cmd == [
        "--db", "data.db",
        "load", "sources/mashkinas",
        "upd/mashkinas_2026-08-24_18-08-16_552252.json",
        "--dt", "1787594896",
    ]
    # глобальная опция --db идёт до подкоманды load
    assert cmd.index("--db") < cmd.index("load")


def test_load_command_honours_dirs():
    cmd = load_command(_cfg(db_path="/abs/x.db", sources_dir="/srv/src"), _sf(), "/in/f.json", 42)
    assert cmd[:5] == ["--db", "/abs/x.db", "load", "/srv/src/mashkinas", "/in/f.json"]


def test_ledger_key_depends_on_name_and_content():
    sf = _sf()
    k1 = ledger_key(sf, b'{"a":1}')
    k2 = ledger_key(sf, b'{"a":2}')
    assert k1 != k2
    assert k1.startswith(sf.filename + ":")
    assert ledger_key(sf, b'{"a":1}') == k1  # детерминирован
