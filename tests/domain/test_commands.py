from src.domain.commands import ingest_command, ledger_key
from src.domain.models import Config
from src.domain.naming import parse_source_file


def _cfg(**kw):
    base = dict(db_path="data.db", sources_dir="sources")
    base.update(kw)
    return Config(**base)


def _sf(name="crm_2026-08-24_18-08-16_552252.json"):
    return parse_source_file(name).value


def test_ingest_command_shape():
    cmd = ingest_command(_cfg(), _sf(), "upd/crm_2026-08-24_18-08-16_552252.json", 1787594896)
    assert cmd == [
        "--db", "data.db",
        "upload", "sources/crm",
        "upd/crm_2026-08-24_18-08-16_552252.json",
        "--dt", "1787594896",
    ]
    # глобальная опция --db идёт до подкоманды upload
    assert cmd.index("--db") < cmd.index("upload")


def test_ingest_command_honours_dirs():
    cmd = ingest_command(_cfg(db_path="/abs/x.db", sources_dir="/srv/src"), _sf(), "/in/f.json", 42)
    assert cmd[:5] == ["--db", "/abs/x.db", "upload", "/srv/src/crm", "/in/f.json"]


def test_ledger_key_depends_on_name_and_content():
    sf = _sf()
    k1 = ledger_key(sf, b'{"a":1}')
    k2 = ledger_key(sf, b'{"a":2}')
    assert k1 != k2
    assert k1.startswith(sf.filename + ":")
    assert ledger_key(sf, b'{"a":1}') == k1  # детерминирован
