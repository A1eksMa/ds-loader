from src.app.ingest import ingest_stage
from src.domain.commands import ledger_key
from src.domain.naming import parse_source_file
from src.ports.ds_cli import CommandResult

from tests.conftest import declare_source

_NAME = "crm_2026-08-24_18-08-16_552252.json"
_NAME2 = "erp_2026-08-24_18-09-00_000000.json"
_OLD = -100.0  # mtime сильно в прошлом -> файл «стабилен»


# --- happy path ---------------------------------------------------------


def test_loads_and_archives(parts):
    declare_source(parts["fs"], "crm")
    parts["fs"].add("sources/crm/upload/" + _NAME, b'{"customer_id":["1"]}', mtime=_OLD)
    ctx = parts["make"]()

    report = ingest_stage(ctx)

    assert report.ok and report.changed == 1
    assert report.outcomes[0].status == "loaded"
    # файл вызвал ds upload (не load -- ingest не доверяет продьюсеру вслепую) ...
    assert parts["ds"].calls == [[
        "--db", "data.db", "upload", "sources/crm",
        "sources/crm/upload/" + _NAME, "--dt", "1787594896",
    ]]
    # ... записан в журнал ...
    key = ledger_key(parse_source_file(_NAME).value, b'{"customer_id":["1"]}')
    assert parts["ledger"].has(key)
    # ... и переехал в архив без микросекунд
    assert "sources/crm/archive/crm_2026-08-24_18-08-16.json" in parts["fs"].files
    assert "sources/crm/upload/" + _NAME not in parts["fs"].files


def test_orders_multiple_files_old_to_new(parts):
    declare_source(parts["fs"], "crm")
    declare_source(parts["fs"], "erp")
    parts["fs"].add("sources/erp/upload/" + _NAME2, mtime=_OLD)   # 18:09:00
    parts["fs"].add("sources/crm/upload/" + _NAME, mtime=_OLD)    # 18:08:16
    ctx = parts["make"]()

    ingest_stage(ctx)

    dt_args = [c[c.index("--dt") + 1] for c in parts["ds"].calls]
    assert dt_args == ["1787594896", "1787594940"]            # старый батч раньше


# --- exactly-once -----------------------------------------------------


def test_second_pass_does_not_reload(parts):
    declare_source(parts["fs"], "crm")
    parts["fs"].add("sources/crm/upload/" + _NAME, mtime=_OLD)
    ctx = parts["make"]()
    ingest_stage(ctx)
    assert len(parts["ds"].calls) == 1

    # тот же файл появился снова (тем же содержимым)
    parts["fs"].add("sources/crm/upload/" + _NAME, mtime=_OLD)
    report = ingest_stage(ctx)

    assert len(parts["ds"].calls) == 1                        # ds повторно НЕ звали
    assert report.outcomes[0].status == "already-loaded"
    assert "sources/crm/archive/crm_2026-08-24_18-08-16.json" in parts["fs"].files


def test_ledger_hit_without_prior_archive_just_files(parts):
    """Крах между записью журнала и перемещением: ключ есть, файл ещё в upload/."""
    declare_source(parts["fs"], "crm")
    sf = parse_source_file(_NAME).value
    content = b'{"x":1}'
    parts["fs"].add("sources/crm/upload/" + _NAME, content, mtime=_OLD)
    parts["ledger"].record(ledger_key(sf, content), {"file": _NAME})
    ctx = parts["make"]()

    report = ingest_stage(ctx)

    assert parts["ds"].calls == []                            # не грузим
    assert report.outcomes[0].status == "already-loaded"
    assert "sources/crm/archive/crm_2026-08-24_18-08-16.json" in parts["fs"].files


# --- partial write ----------------------------------------------------


def test_skips_file_still_being_written(parts):
    declare_source(parts["fs"], "crm")
    # mtime «сейчас» -> моложе stable_after_seconds -> пропуск до следующего тика
    parts["fs"].add("sources/crm/upload/" + _NAME, mtime=parts["clock"].now())
    ctx = parts["make"]()

    report = ingest_stage(ctx)

    assert parts["ds"].calls == []
    assert report.changed == 0
    assert report.outcomes[0].status == "skipped-unstable"
    assert "sources/crm/upload/" + _NAME in parts["fs"].files  # остался на месте


def test_stable_file_after_time_passes(parts):
    declare_source(parts["fs"], "crm")
    parts["fs"].add("sources/crm/upload/" + _NAME, mtime=parts["clock"].now() - 5.0)
    ctx = parts["make"]()
    report = ingest_stage(ctx)
    assert report.outcomes[0].status == "loaded"


# --- прогресс в реальном времени (ctx.log) --------------------------------


def test_logs_progress_per_file_as_it_happens(parts):
    """Не только итоговый StageReport в конце — каждый файл отмечается в логе сразу же
    (начало обработки, вызов ds upload, результат), чтобы долгую пачку/большой файл не
    приняли за зависание."""
    declare_source(parts["fs"], "crm")
    declare_source(parts["fs"], "erp")
    parts["fs"].add("sources/crm/upload/" + _NAME, mtime=_OLD)
    parts["fs"].add("sources/erp/upload/" + _NAME2, mtime=_OLD)

    ingest_stage(parts["make"]())

    logs = parts["logs"]
    assert any("к обработке 2 файл" in m for m in logs)
    assert any("[1/2]" in m and "crm/" + _NAME in m and "начинаю" in m for m in logs)
    assert any("crm/" + _NAME in m and "вызываю ds upload" in m for m in logs)
    assert any("[1/2]" in m and "loaded" in m for m in logs)
    assert any("[2/2]" in m and "erp/" + _NAME2 in m for m in logs)


def test_no_progress_log_when_nothing_to_process(parts):
    declare_source(parts["fs"], "crm")
    ingest_stage(parts["make"]())
    assert parts["logs"] == []


# --- upload/ автосоздаётся -----------------------------------------------


def test_upload_dir_created_if_missing(parts):
    declare_source(parts["fs"], "crm")            # только source.json, upload/ ещё нет
    ctx = parts["make"]()

    report = ingest_stage(ctx)

    assert report.ok and report.changed == 0
    assert "sources/crm/upload" in parts["fs"].dirs


# --- failures -------------------------------------------------------


def test_ds_failure_quarantines(parts):
    declare_source(parts["fs"], "crm")
    parts["fs"].add("sources/crm/upload/" + _NAME, mtime=_OLD)
    parts["ds"].result = CommandResult(1, "", "Source not found: crm")
    ctx = parts["make"]()

    report = ingest_stage(ctx)

    assert report.changed == 0
    assert report.outcomes[0].status == "quarantined"
    assert "sources/crm/quarantine/" + _NAME in parts["fs"].files
    assert "sources/crm/quarantine/" + _NAME + ".err" in parts["fs"].files
    assert parts["ledger"].entries == {}                      # в журнал НЕ пишем
    assert "sources/crm/upload/" + _NAME not in parts["fs"].files


def test_bad_name_is_reported_not_processed(parts):
    declare_source(parts["fs"], "crm")
    parts["fs"].add("sources/crm/upload/garbage.json", mtime=_OLD)
    parts["fs"].add("sources/crm/upload/" + _NAME, mtime=_OLD)
    ctx = parts["make"]()

    report = ingest_stage(ctx)

    assert parts["ds"].calls and parts["ds"].calls[0][3] == "sources/crm"
    assert any("skipped-name" in line for line in report.lines)
    assert "sources/crm/upload/garbage.json" in parts["fs"].files   # чужой файл не трогаем


def test_bad_timestamp_quarantines_without_ds_call(parts):
    declare_source(parts["fs"], "crm")
    # синтаксически валидное имя, но невозможная дата
    name = "crm_2026-13-40_99-99-99_000000.json"
    parts["fs"].add("sources/crm/upload/" + name, mtime=_OLD)
    ctx = parts["make"]()

    report = ingest_stage(ctx)

    assert parts["ds"].calls == []
    assert report.outcomes[0].status == "quarantined"


def test_misfiled_file_is_reported_not_processed(parts):
    """Имя файла заявляет источник 'erp', а лежит в upload/ источника 'crm' — не трогаем,
    не грузим под чужим source_dir."""
    declare_source(parts["fs"], "crm")
    parts["fs"].add("sources/crm/upload/" + _NAME2, mtime=_OLD)   # erp_... лежит у crm

    report = ingest_stage(parts["make"]())

    assert parts["ds"].calls == []
    assert any("skipped-misfiled" in line for line in report.lines)
    assert "sources/crm/upload/" + _NAME2 in parts["fs"].files    # не трогаем


def test_source_without_source_json_is_not_scanned(parts):
    """Поддиректория sources_dir без source.json не считается источником."""
    parts["fs"].mkdir("sources/mystery")
    parts["fs"].add("sources/mystery/upload/" + _NAME, mtime=_OLD)

    report = ingest_stage(parts["make"]())

    assert report.ok and report.changed == 0
    assert parts["ds"].calls == []
    assert "sources/mystery/upload/" + _NAME in parts["fs"].files


def test_missing_sources_dir_reports_not_ok(parts):
    ctx = parts["make"]()
    parts["fs"].dirs.discard("sources")
    report = ingest_stage(ctx)
    assert report.ok is False and report.changed == 0
