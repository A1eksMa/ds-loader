import json

from src.config.loader import load_config
from src.domain.result import Err, Ok


def test_defaults_with_only_update_dir():
    r = load_config(None, {"update_dir": "upd"})
    assert isinstance(r, Ok)
    cfg = r.value
    assert cfg.update_dir == "upd"
    assert cfg.db_path == "data.db"
    assert cfg.sources_dir == "sources"
    assert cfg.stages == ("ingest",)
    assert cfg.ds_command == ("ds",)
    assert cfg.filename_tz == "utc"


def test_requires_update_dir():
    assert isinstance(load_config(None, {}), Err)


def test_file_then_overrides(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({
        "update_dir": "/data/upd",
        "db_path": "/data/data.db",
        "poll_interval_seconds": 10,
        "ds_command": ["python", "-m", "src.cli.commands"],
        "sources": {"crm": {"prep_cmd": ["prep", "crm"]}},
    }), encoding="utf-8")

    r = load_config(str(p), {"db_path": "/override/data.db", "sources_dir": None})
    assert isinstance(r, Ok)
    cfg = r.value
    assert cfg.update_dir == "/data/upd"
    assert cfg.db_path == "/override/data.db"          # CLI перекрыл файл
    assert cfg.sources_dir == "sources"               # None-override не применяется
    assert cfg.poll_interval_seconds == 10.0
    assert cfg.ds_command == ("python", "-m", "src.cli.commands")
    assert cfg.sources["crm"].prep_cmd == ("prep", "crm")


def test_rejects_unknown_stage(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"update_dir": "upd", "stages": ["ingest", "publish"]}), encoding="utf-8")
    r = load_config(str(p), {})
    assert isinstance(r, Err) and "publish" in r.error


def test_rejects_bad_tz():
    assert isinstance(load_config(None, {"update_dir": "upd", "filename_tz": "mars"}), Err)


def test_rejects_nonpositive_interval():
    assert isinstance(load_config(None, {"update_dir": "upd", "poll_interval_seconds": 0}), Err)


def test_missing_config_file_is_err(tmp_path):
    assert isinstance(load_config(str(tmp_path / "nope.json"), {"update_dir": "upd"}), Err)
