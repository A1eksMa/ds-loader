import json

from src.cli.main import main

_NAME = "crm_2026-08-24_18-08-16_552252.json"


def _write_config(tmp_path, **extra):
    cfg = {
        "update_dir": str(tmp_path / "upd"),
        "archive_dir": str(tmp_path / "archive"),
        "quarantine_dir": str(tmp_path / "quarantine"),
        "ledger_path": str(tmp_path / "ledger.jsonl"),
        "ds_command": ["true"],          # /usr/bin/true: игнорирует argv, код 0
        "stable_after_seconds": 0.0,
    }
    cfg.update(extra)
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    return p


def test_run_once_happy_path(tmp_path, capsys):
    (tmp_path / "upd").mkdir()
    (tmp_path / "upd" / _NAME).write_text('{"customer_id":["1"]}', encoding="utf-8")
    cfg = _write_config(tmp_path)

    rc = main(["run", "--once", "--config", str(cfg)])

    assert rc == 0
    assert (tmp_path / "archive" / "crm" / "crm_2026-08-24_18-08-16.json").exists()
    assert not (tmp_path / "upd" / _NAME).exists()
    assert (tmp_path / "ledger.jsonl").exists()
    out = capsys.readouterr().out
    assert "[ingest]" in out and "changed=1" in out


def test_run_once_ds_failure_quarantines(tmp_path):
    (tmp_path / "upd").mkdir()
    (tmp_path / "upd" / _NAME).write_text("{}", encoding="utf-8")
    cfg = _write_config(tmp_path, ds_command=["false"])   # код 1

    rc = main(["run", "--once", "--config", str(cfg)])

    assert rc == 0                                        # тик как таковой отработал
    assert (tmp_path / "quarantine" / "crm" / _NAME).exists()
    assert not (tmp_path / "ledger.jsonl").exists()


def test_run_missing_update_dir_is_config_error(tmp_path, capsys):
    rc = main(["run", "--once"])
    assert rc == 1
    assert "update_dir" in capsys.readouterr().err


def test_run_once_wires_publish_stage(tmp_path, capsys):
    (tmp_path / "upd").mkdir()
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


def test_cli_override_beats_config(tmp_path):
    (tmp_path / "upd2").mkdir()
    (tmp_path / "upd2" / _NAME).write_text("{}", encoding="utf-8")
    cfg = _write_config(tmp_path)  # update_dir points at .../upd (does not exist)

    rc = main(["run", "--once", "--config", str(cfg), "--update-dir", str(tmp_path / "upd2")])

    assert rc == 0
    assert (tmp_path / "archive" / "crm" / "crm_2026-08-24_18-08-16.json").exists()
