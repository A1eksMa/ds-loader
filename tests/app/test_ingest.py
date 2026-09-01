from src.app.ingest import ingest_stage
from src.domain.commands import ledger_key
from src.domain.naming import parse_source_file
from src.ports.ds_cli import CommandResult

_NAME = "mashkinas_2026-08-24_18-08-16_552252.json"
_NAME2 = "erp_2026-08-24_18-09-00_000000.json"
_OLD = -100.0  # mtime сильно в прошлом -> файл «стабилен»


# --- happy path ---------------------------------------------------------


def test_loads_and_archives(parts):
    parts["fs"].add("upd/" + _NAME, b'{"customer_id":["1"]}', mtime=_OLD)
    ctx = parts["make"]()

    report = ingest_stage(ctx)

    assert report.ok and report.changed == 1
    assert report.outcomes[0].status == "loaded"
    # файл вызвал ds load ...
    assert parts["ds"].calls == [[
        "--db", "data.db", "load", "sources/mashkinas",
        "upd/" + _NAME, "--dt", "1787594896",
    ]]
    # ... записан в журнал ...
    key = ledger_key(parse_source_file(_NAME).value, b'{"customer_id":["1"]}')
    assert parts["ledger"].has(key)
    # ... и переехал в архив без микросекунд
    assert "archive/mashkinas/mashkinas_2026-08-24_18-08-16.json" in parts["fs"].files
    assert "upd/" + _NAME not in parts["fs"].files


def test_orders_multiple_files_old_to_new(parts):
    parts["fs"].add("upd/" + _NAME2, mtime=_OLD)              # 18:09:00
    parts["fs"].add("upd/" + _NAME, mtime=_OLD)               # 18:08:16
    ctx = parts["make"]()

    ingest_stage(ctx)

    dt_args = [c[c.index("--dt") + 1] for c in parts["ds"].calls]
    assert dt_args == ["1787594896", "1787594940"]            # старый батч раньше


# --- exactly-once -----------------------------------------------------


def test_second_pass_does_not_reload(parts):
    parts["fs"].add("upd/" + _NAME, mtime=_OLD)
    ctx = parts["make"]()
    ingest_stage(ctx)
    assert len(parts["ds"].calls) == 1

    # тот же файл появился снова (тем же содержимым)
    parts["fs"].add("upd/" + _NAME, mtime=_OLD)
    report = ingest_stage(ctx)

    assert len(parts["ds"].calls) == 1                        # ds повторно НЕ звали
    assert report.outcomes[0].status == "already-loaded"
    assert "archive/mashkinas/mashkinas_2026-08-24_18-08-16.json" in parts["fs"].files


def test_ledger_hit_without_prior_archive_just_files(parts):
    """Крах между записью журнала и перемещением: ключ есть, файл ещё в upd/."""
    sf = parse_source_file(_NAME).value
    content = b'{"x":1}'
    parts["fs"].add("upd/" + _NAME, content, mtime=_OLD)
    parts["ledger"].record(ledger_key(sf, content), {"file": _NAME})
    ctx = parts["make"]()

    report = ingest_stage(ctx)

    assert parts["ds"].calls == []                            # не грузим
    assert report.outcomes[0].status == "already-loaded"
    assert "archive/mashkinas/mashkinas_2026-08-24_18-08-16.json" in parts["fs"].files


# --- partial write ----------------------------------------------------


def test_skips_file_still_being_written(parts):
    # mtime «сейчас» -> моложе stable_after_seconds -> пропуск до следующего тика
    parts["fs"].add("upd/" + _NAME, mtime=parts["clock"].now())
    ctx = parts["make"]()

    report = ingest_stage(ctx)

    assert parts["ds"].calls == []
    assert report.changed == 0
    assert report.outcomes[0].status == "skipped-unstable"
    assert "upd/" + _NAME in parts["fs"].files                # остался на месте


def test_stable_file_after_time_passes(parts):
    parts["fs"].add("upd/" + _NAME, mtime=parts["clock"].now() - 5.0)
    ctx = parts["make"]()
    report = ingest_stage(ctx)
    assert report.outcomes[0].status == "loaded"


# --- failures -------------------------------------------------------


def test_ds_failure_quarantines(parts):
    parts["fs"].add("upd/" + _NAME, mtime=_OLD)
    parts["ds"].result = CommandResult(1, "", "Source not found: mashkinas")
    ctx = parts["make"]()

    report = ingest_stage(ctx)

    assert report.changed == 0
    assert report.outcomes[0].status == "quarantined"
    assert "quarantine/mashkinas/" + _NAME in parts["fs"].files
    assert "quarantine/mashkinas/" + _NAME + ".err" in parts["fs"].files
    assert parts["ledger"].entries == {}                      # в журнал НЕ пишем
    assert "upd/" + _NAME not in parts["fs"].files


def test_bad_name_is_reported_not_processed(parts):
    parts["fs"].add("upd/garbage.json", mtime=_OLD)
    parts["fs"].add("upd/" + _NAME, mtime=_OLD)
    ctx = parts["make"]()

    report = ingest_stage(ctx)

    assert parts["ds"].calls and parts["ds"].calls[0][3] == "sources/mashkinas"
    assert any("skipped-name" in line for line in report.lines)
    assert "upd/garbage.json" in parts["fs"].files            # чужой файл не трогаем


def test_bad_timestamp_quarantines_without_ds_call(parts):
    # синтаксически валидное имя, но невозможная дата
    name = "mashkinas_2026-13-40_99-99-99_000000.json"
    parts["fs"].add("upd/" + name, mtime=_OLD)
    ctx = parts["make"]()

    report = ingest_stage(ctx)

    assert parts["ds"].calls == []
    assert report.outcomes[0].status == "quarantined"


def test_missing_update_dir_reports_not_ok(parts):
    ctx = parts["make"]()
    parts["fs"].dirs.discard("upd")
    report = ingest_stage(ctx)
    assert report.ok is False and report.changed == 0
