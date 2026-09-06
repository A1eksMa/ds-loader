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
    p.write_text(json.dumps({"update_dir": "upd", "stages": ["ingest", "bogus"]}), encoding="utf-8")
    r = load_config(str(p), {})
    assert isinstance(r, Err) and "bogus" in r.error


def test_publish_stage_requires_webui_data_dir():
    r = load_config(None, {"update_dir": "upd", "stages": ["ingest", "publish"]})
    assert isinstance(r, Err) and "webui_data_dir" in r.error


def test_publish_stage_ok_with_webui_data_dir():
    r = load_config(None, {
        "update_dir": "upd", "stages": ["ingest", "publish"], "webui_data_dir": "webui/data",
    })
    assert isinstance(r, Ok)
    assert r.value.stages == ("ingest", "publish")
    assert r.value.webui_data_dir == "webui/data"
    assert r.value.publish_state_path == ".ds-loader/publish.json"   # дефолт


def test_webui_keys_from_file(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({
        "update_dir": "upd", "stages": ["publish"], "webui_data_dir": "w",
        "webui_preset": "preset.json", "publish_state_path": "state.json",
    }), encoding="utf-8")
    r = load_config(str(p), {})
    assert isinstance(r, Ok)
    assert r.value.webui_preset == "preset.json"
    assert r.value.publish_state_path == "state.json"


def test_rejects_bad_tz():
    assert isinstance(load_config(None, {"update_dir": "upd", "filename_tz": "mars"}), Err)


def test_rejects_nonpositive_interval():
    assert isinstance(load_config(None, {"update_dir": "upd", "poll_interval_seconds": 0}), Err)


def test_missing_config_file_is_err(tmp_path):
    assert isinstance(load_config(str(tmp_path / "nope.json"), {"update_dir": "upd"}), Err)


def test_ds_pythonpath_defaults_to_none():
    r = load_config(None, {"update_dir": "upd"})
    assert isinstance(r, Ok) and r.value.ds_pythonpath is None


def test_ds_pythonpath_from_file_and_override(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"update_dir": "upd", "ds_pythonpath": "/opt/ds"}), encoding="utf-8")

    assert load_config(str(p), {}).value.ds_pythonpath == "/opt/ds"
    assert load_config(str(p), {"ds_pythonpath": "/other/ds"}).value.ds_pythonpath == "/other/ds"
    # None-override не сбрасывает значение из файла
    assert load_config(str(p), {"ds_pythonpath": None}).value.ds_pythonpath == "/opt/ds"
