import json

from src.app.context import Context
from src.app.publish import publish_stage
from src.domain.models import Config
from src.ports.ds_cli import CommandResult


def _payload(name, gen=8, labels=("email",), rows=1):
    return {
        "meta": {
            "name": name, "key": "id", "as_of": 100.0, "generated_at": 200.0,
            "gen_max_cnt": gen, "include_archive": False, "rows": rows,
            "labels": list(labels),
        },
        "data": [{"id": "1", "email": "a@x"}],
    }


def _ctx(parts, **cfg_kw):
    base = dict(update_dir="upd", db_path="data.db",
                webui_data_dir="webui/data", stages=("publish",))
    base.update(cfg_kw)
    return Context(
        config=Config(**base), clock=parts["clock"], fs=parts["fs"],
        ds=parts["ds"], ledger=parts["ledger"], stages=(), log=lambda _m: None,
    )


def _manifest(fs):
    txt = fs.files["webui/data/manifest.js"][0].decode("utf-8")
    return json.loads(txt.split("window.DS_MANIFEST = ", 1)[1].rstrip()[:-1])


def test_writes_all_sources_and_manifest(parts):
    parts["ds"].result = CommandResult(
        0, json.dumps({"CRM": _payload("CRM"), "ERP": _payload("ERP", gen=5)}), "")

    rep = publish_stage(_ctx(parts))

    assert rep.ok and rep.changed == 2
    fs = parts["fs"]
    assert "webui/data/CRM.js" in fs.files
    assert "webui/data/ERP.js" in fs.files
    doc = _manifest(fs)
    assert {s["name"] for s in doc["sources"]} == {"CRM", "ERP"}
    assert doc["db_max_cnt"] == 8                      # max gen_max_cnt по источникам
    assert all(s["db_max_cnt"] == s["gen_max_cnt"] for s in doc["sources"])
    assert ".ds-loader/publish.json" in fs.files       # отпечатки сохранены


def test_second_run_without_changes_writes_nothing(parts):
    parts["ds"].result = CommandResult(0, json.dumps({"CRM": _payload("CRM")}), "")
    ctx = _ctx(parts)
    publish_stage(ctx)
    before = dict(parts["fs"].files)

    rep = publish_stage(ctx)

    assert rep.ok and rep.changed == 0
    assert parts["fs"].files == before                 # ни один файл не тронут
    assert "без изменений" in rep.lines


def test_only_changed_source_is_rebuilt(parts):
    parts["ds"].result = CommandResult(
        0, json.dumps({"CRM": _payload("CRM", gen=8), "ERP": _payload("ERP", gen=5)}), "")
    ctx = _ctx(parts)
    publish_stage(ctx)
    crm_before = parts["fs"].files["webui/data/CRM.js"]
    erp_before = parts["fs"].files["webui/data/ERP.js"]

    parts["ds"].result = CommandResult(
        0, json.dumps({"CRM": _payload("CRM", gen=12), "ERP": _payload("ERP", gen=5)}), "")
    rep = publish_stage(ctx)

    assert rep.changed == 1
    assert rep.lines[0] == "CRM: пересобран"
    assert parts["fs"].files["webui/data/CRM.js"] != crm_before
    assert parts["fs"].files["webui/data/ERP.js"] == erp_before


def test_ds_get_failure_reports_not_ok_and_writes_nothing(parts):
    parts["ds"].result = CommandResult(1, "", "Source not found: X")

    rep = publish_stage(_ctx(parts))

    assert not rep.ok and rep.changed == 0
    assert parts["fs"].files == {}
    assert rep.lines[0].startswith("ds get:")


def test_empty_db_writes_empty_manifest(parts):
    parts["ds"].result = CommandResult(0, "{}", "")

    rep = publish_stage(_ctx(parts))

    assert rep.ok and rep.changed == 0
    doc = _manifest(parts["fs"])
    assert doc["sources"] == [] and doc["db_max_cnt"] == 0


def test_dropped_source_removed_from_manifest(parts):
    parts["ds"].result = CommandResult(
        0, json.dumps({"CRM": _payload("CRM"), "ERP": _payload("ERP")}), "")
    ctx = _ctx(parts)
    publish_stage(ctx)

    parts["ds"].result = CommandResult(0, json.dumps({"CRM": _payload("CRM")}), "")
    rep = publish_stage(ctx)

    assert rep.changed == 0
    assert {s["name"] for s in _manifest(parts["fs"])["sources"]} == {"CRM"}
    assert "ERP: выбыл из выборки" in rep.lines


def test_corrupt_state_file_triggers_full_rebuild(parts):
    # путь состояния по умолчанию — .ds-loader/publish.json
    parts["fs"].write_text(".ds-loader/publish.json", "{ not json")
    parts["ds"].result = CommandResult(0, json.dumps({"CRM": _payload("CRM")}), "")

    rep = publish_stage(_ctx(parts))

    assert rep.ok and rep.changed == 1                 # битое состояние => пересобрали всё
