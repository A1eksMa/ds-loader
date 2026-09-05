"""SubprocessDsCli реально запускает подпроцесс — проверяем через python3 -c."""
import os
import sys

from src.adapters.subprocess_ds_cli import SubprocessDsCli

_PRINT_PP = [sys.executable, "-c", "import os,sys; sys.stdout.write(os.environ.get('PYTHONPATH',''))"]


def test_passes_args_and_captures_output():
    ds = SubprocessDsCli([sys.executable, "-c", "import sys; print('hi', *sys.argv[1:])"])
    res = ds.run(["load", "x"])
    assert res.exit_code == 0
    assert res.stdout.strip() == "hi load x"


def test_nonzero_exit_is_not_an_exception():
    ds = SubprocessDsCli([sys.executable, "-c", "import sys; sys.stderr.write('boom'); sys.exit(3)"])
    res = ds.run([])
    assert res.exit_code == 3
    assert res.stderr.strip() == "boom"


def test_without_pythonpath_inherits_env(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/inherited/path")
    ds = SubprocessDsCli(_PRINT_PP)
    assert ds.run([]).stdout == "/inherited/path"


def test_pythonpath_replaces_inherited(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/loader/src")
    ds = SubprocessDsCli(_PRINT_PP, pythonpath="/opt/ds")
    assert ds.run([]).stdout == "/opt/ds"      # заменяет, не добавляет


def test_pythonpath_set_when_absent_in_parent(monkeypatch):
    monkeypatch.delenv("PYTHONPATH", raising=False)
    ds = SubprocessDsCli(_PRINT_PP, pythonpath="/opt/ds")
    assert ds.run([]).stdout == "/opt/ds"


def test_other_env_still_inherited(monkeypatch):
    monkeypatch.setenv("DS_LOADER_MARKER", "kept")
    ds = SubprocessDsCli(
        [sys.executable, "-c", "import os,sys; sys.stdout.write(os.environ.get('DS_LOADER_MARKER',''))"],
        pythonpath="/opt/ds",
    )
    assert ds.run([]).stdout == "kept"
