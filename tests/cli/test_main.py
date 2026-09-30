import json
import sys

from src.cli.main import main

_NAME = "crm_2026-08-24_18-08-16_552252.json"


def _write_config(tmp_path, **extra):
    cfg = {
        "sources_dir": str(tmp_path / "sources"),
        "ledger_path": str(tmp_path / "ledger.jsonl"),
        "ds_command": ["true"],          # /usr/bin/true: игнорирует argv, код 0
        "stable_after_seconds": 0.0,
    }
    cfg.update(extra)
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    return p


def _declare_source(tmp_path, name, sources_dir=None):
    root = sources_dir or (tmp_path / "sources")
    (root / name).mkdir(parents=True)
    (root / name / "source.json").write_text(json.dumps({"name": name}), encoding="utf-8")
    return root / name


def test_run_once_happy_path(tmp_path, capsys):
    crm = _declare_source(tmp_path, "crm")
    (crm / "upload").mkdir()
    (crm / "upload" / _NAME).write_text('{"customer_id":["1"]}', encoding="utf-8")
    cfg = _write_config(tmp_path)

    rc = main(["run", "--once", "--config", str(cfg)])

    assert rc == 0
    assert (crm / "archive" / "crm_2026-08-24_18-08-16.json").exists()
    assert not (crm / "upload" / _NAME).exists()
    assert (tmp_path / "ledger.jsonl").exists()
    out = capsys.readouterr().out
    assert "[ingest]" in out and "changed=1" in out


def test_run_once_ds_failure_quarantines(tmp_path):
    crm = _declare_source(tmp_path, "crm")
    (crm / "upload").mkdir()
    (crm / "upload" / _NAME).write_text("{}", encoding="utf-8")
    cfg = _write_config(tmp_path, ds_command=["false"])   # код 1

    rc = main(["run", "--once", "--config", str(cfg)])

    assert rc == 0                                        # тик как таковой отработал
    assert (crm / "quarantine" / _NAME).exists()
    assert not (tmp_path / "ledger.jsonl").exists()


def test_run_missing_sources_dir_reports_stage_failure(tmp_path, capsys):
    # sources_dir указан, но не существует на диске -- ошибка стадии, не конфига
    cfg = _write_config(tmp_path, sources_dir=str(tmp_path / "nope"))

    rc = main(["run", "--once", "--config", str(cfg)])

    assert rc == 0                                        # тик отработал, просто стадия FAIL
    out = capsys.readouterr().out
    assert "[ingest] FAIL" in out
    assert "источников недоступна" in out


def test_run_once_wires_publish_stage(tmp_path, capsys):
    (tmp_path / "sources").mkdir()
    cfg = _write_config(
        tmp_path,
        stages=["ingest", "publish"],
        webui_data_dir=str(tmp_path / "webui" / "data"),
    )

    rc = main(["run", "--once", "--config", str(cfg)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "[ingest] ok" in out
    assert "[publish] FAIL" in out          # `true` не отдаёт вывод для ds get


def test_publish_stage_needs_webui_data_dir(tmp_path, capsys):
    cfg = _write_config(tmp_path, stages=["ingest", "publish"])

    rc = main(["run", "--once", "--config", str(cfg)])

    assert rc == 1
    assert "webui_data_dir" in capsys.readouterr().err


def test_force_publish_flag_rewrites_unchanged_manifest(tmp_path, capsys):
    crm = _declare_source(tmp_path, "CRM")
    (crm / "source.json").write_text(
        json.dumps({"name": "CRM", "key_label": "customer_id",
                    "labels": [{"name": "email", "type": "text", "publish": True}]}),
        encoding="utf-8",
    )
    ds_stub = tmp_path / "ds_get.py"
    ds_stub.write_text(
        "import sys, json\n"
        "print(json.dumps({'meta': {'name': 'CRM', 'key': 'customer_id', 'gen_max_cnt': 1, "
        "'rows': 1, 'labels': ['email']}, 'data': [{'customer_id': '1', 'email': 'a@x'}]}))\n",
        encoding="utf-8",
    )
    cfg = _write_config(
        tmp_path, stages=["publish"],
        webui_data_dir=str(tmp_path / "webui" / "data"),
        publish_state_path=str(tmp_path / ".ds-loader" / "publish.json"),
        ds_command=[sys.executable, str(ds_stub)],
    )

    def _sources():
        js = (tmp_path / "webui" / "data" / "manifest.js").read_text(encoding="utf-8")
        return json.loads(js.split("window.DS_MANIFEST = ", 1)[1].rstrip()[:-1])["sources"]

    rc = main(["run", "--once", "--config", str(cfg)])
    assert rc == 0
    sources_before = _sources()
    assert "CRM: пересобран" in capsys.readouterr().out

    rc = main(["run", "--once", "--config", str(cfg)])
    assert "без изменений" in capsys.readouterr().out    # обычный тик: ничего не поменялось

    rc = main(["run", "--once", "--config", str(cfg), "--force-publish"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "--force-publish" in out and "CRM: пересобран" in out
    assert _sources() == sources_before          # содержимое то же, БД не трогали


def test_cli_override_beats_config(tmp_path):
    other_root = tmp_path / "elsewhere"
    crm = _declare_source(tmp_path, "crm", sources_dir=other_root)
    (crm / "upload").mkdir()
    (crm / "upload" / _NAME).write_text("{}", encoding="utf-8")
    cfg = _write_config(tmp_path)   # sources_dir конфига (tmp_path/sources) не существует

    rc = main(["run", "--once", "--config", str(cfg), "--sources-dir", str(other_root)])

    assert rc == 0
    assert (crm / "archive" / "crm_2026-08-24_18-08-16.json").exists()
