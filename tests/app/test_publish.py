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
    base = dict(db_path="data.db",
                webui_data_dir="webui/data", stages=("publish",))
    base.update(cfg_kw)
    return Context(
        config=Config(**base), clock=parts["clock"], fs=parts["fs"],
        ds=parts["ds"], ledger=parts["ledger"], stages=(), log=lambda _m: None,
    )


def _manifest(fs):
    txt = fs.files["webui/data/manifest.js"][0].decode("utf-8")
    return json.loads(txt.split("window.DS_MANIFEST = ", 1)[1].rstrip()[:-1])


def _declare_source(fs, name, labels, sources_dir="sources", description=None):
    """labels: [(имя, type, publish)] -> sources_dir/<name>/source.json."""
    doc = {
        "name": name, "key_label": "id",
        "labels": [{"name": n, "type": t, "publish": p} for n, t, p in labels],
    }
    if description is not None:
        doc["description"] = description
    fs.write_text(sources_dir + "/" + name + "/source.json", json.dumps(doc))


def test_writes_all_sources_and_manifest(parts):
    _declare_source(parts["fs"], "CRM", [("email", "text", True)])
    _declare_source(parts["fs"], "ERP", [("email", "text", True)])
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
    assert all(s["labels"] == ["email"] for s in doc["sources"])
    assert ".ds-loader/publish.json" in fs.files       # отпечатки сохранены


def test_second_run_without_changes_writes_nothing(parts):
    _declare_source(parts["fs"], "CRM", [("email", "text", True)])
    parts["ds"].result = CommandResult(0, json.dumps({"CRM": _payload("CRM")}), "")
    ctx = _ctx(parts)
    publish_stage(ctx)
    before = dict(parts["fs"].files)

    rep = publish_stage(ctx)

    assert rep.ok and rep.changed == 0
    assert parts["fs"].files == before                 # ни один файл не тронут
    assert "без изменений" in rep.lines


def test_only_changed_source_is_rebuilt(parts):
    _declare_source(parts["fs"], "CRM", [("email", "text", True)])
    _declare_source(parts["fs"], "ERP", [("email", "text", True)])
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
    _declare_source(parts["fs"], "CRM", [("email", "text", True)])
    _declare_source(parts["fs"], "ERP", [("email", "text", True)])
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
    _declare_source(parts["fs"], "CRM", [("email", "text", True)])
    # путь состояния по умолчанию — .ds-loader/publish.json
    parts["fs"].write_text(".ds-loader/publish.json", "{ not json")
    parts["ds"].result = CommandResult(0, json.dumps({"CRM": _payload("CRM")}), "")

    rep = publish_stage(_ctx(parts))

    assert rep.ok and rep.changed == 1                 # битое состояние => пересобрали всё


# --- фильтрация по source.json: publish-флаги и type -----------------------


def test_source_without_source_json_publishes_only_key_column(parts):
    parts["ds"].result = CommandResult(0, json.dumps({"CRM": _payload("CRM")}), "")

    rep = publish_stage(_ctx(parts))

    assert rep.ok and rep.changed == 1
    js = parts["fs"].files["webui/data/CRM.js"][0].decode("utf-8")
    body = json.loads(js.split("] = ", 1)[1].rstrip()[:-1])
    assert body["meta"]["labels"] == []
    assert body["data"] == [{"id": "1"}]
    doc = _manifest(parts["fs"])
    assert doc["sources"][0]["labels"] == []
    assert doc["sources"][0]["label_types"] == {}


def test_unpublished_label_is_filtered_out(parts):
    _declare_source(parts["fs"], "CRM", [("email", "text", False)])
    parts["ds"].result = CommandResult(0, json.dumps({"CRM": _payload("CRM")}), "")

    publish_stage(_ctx(parts))

    doc = _manifest(parts["fs"])
    assert doc["sources"][0]["labels"] == []


def test_label_types_included_in_manifest(parts):
    _declare_source(parts["fs"], "CRM", [("email", "number", True)])
    parts["ds"].result = CommandResult(0, json.dumps({"CRM": _payload("CRM")}), "")

    publish_stage(_ctx(parts))

    doc = _manifest(parts["fs"])
    assert doc["sources"][0]["label_types"] == {"email": "number"}


def test_description_included_in_manifest(parts):
    _declare_source(
        parts["fs"], "CRM", [("email", "text", True)],
        description="CRM, выгрузка из 1С раз в сутки",
    )
    parts["ds"].result = CommandResult(0, json.dumps({"CRM": _payload("CRM")}), "")

    publish_stage(_ctx(parts))

    doc = _manifest(parts["fs"])
    assert doc["sources"][0]["description"] == "CRM, выгрузка из 1С раз в сутки"


def test_source_without_description_is_none_in_manifest(parts):
    _declare_source(parts["fs"], "CRM", [("email", "text", True)])   # без description
    parts["ds"].result = CommandResult(0, json.dumps({"CRM": _payload("CRM")}), "")

    publish_stage(_ctx(parts))

    doc = _manifest(parts["fs"])
    assert doc["sources"][0]["description"] is None


def test_force_publish_rewrites_unchanged_sources(parts):
    _declare_source(parts["fs"], "CRM", [("email", "text", True)])
    parts["ds"].result = CommandResult(0, json.dumps({"CRM": _payload("CRM")}), "")
    ctx = _ctx(parts)
    publish_stage(ctx)
    crm_before = parts["fs"].files["webui/data/CRM.js"]

    # тот же payload, БД не менялась — обычный тик ничего бы не тронул
    rep = publish_stage(_ctx(parts, force_publish=True))

    assert rep.ok and rep.changed == 1
    assert "CRM: пересобран" in rep.lines
    assert rep.lines[0] == "--force-publish: сохранённые отпечатки проигнорированы"
    assert parts["fs"].files["webui/data/CRM.js"] == crm_before   # содержимое то же, но записано заново


def test_force_publish_does_not_change_state_semantics_for_next_normal_run(parts):
    _declare_source(parts["fs"], "CRM", [("email", "text", True)])
    parts["ds"].result = CommandResult(0, json.dumps({"CRM": _payload("CRM")}), "")
    ctx = _ctx(parts)
    publish_stage(_ctx(parts, force_publish=True))

    rep = publish_stage(ctx)                            # обычный тик сразу после форс-прогона

    assert rep.changed == 0 and "без изменений" in rep.lines


def test_publishing_a_previously_hidden_label_triggers_rewrite(parts):
    """Смена publish-флага в source.json меняет сигнатуру, даже если `ds get`
    вернул тот же payload — без этого правки source.json «повисали» бы до
    следующего фактического изменения данных источника."""
    parts["ds"].result = CommandResult(0, json.dumps({"CRM": _payload("CRM")}), "")
    ctx = _ctx(parts)
    publish_stage(ctx)                                  # без source.json -> labels == []
    assert _manifest(parts["fs"])["sources"][0]["labels"] == []

    _declare_source(parts["fs"], "CRM", [("email", "text", True)])
    rep = publish_stage(ctx)

    assert rep.changed == 1
    assert _manifest(parts["fs"])["sources"][0]["labels"] == ["email"]
