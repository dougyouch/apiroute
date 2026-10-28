import subprocess
from pathlib import Path

from apiroute.codegen import source_formatter
from apiroute.codegen.source_formatter import SourceFormatter


def test_many_files_are_formatted_in_batches(monkeypatch):
    calls = []
    monkeypatch.setattr(source_formatter.shutil, "which", lambda name: "/bin/ruff")
    monkeypatch.setattr(
        source_formatter.subprocess,
        "run",
        lambda command, check: calls.append(command) or subprocess.CompletedProcess(command, 0),
    )
    paths = [Path(f"pkg/m{index}.py") for index in range(1201)]
    assert SourceFormatter().format(paths)
    files = [[arg for arg in call if arg.endswith(".py")] for call in calls]
    assert [call[1] for call in calls] == ["check", "format"] * 3
    assert [len(batch) for batch in files] == [500, 500, 500, 500, 201, 201]
    assert files[0] == files[1] and sum(map(len, files[::2])) == 1201


def test_a_failing_batch_stops_formatting(monkeypatch):
    calls = []
    monkeypatch.setattr(source_formatter.shutil, "which", lambda name: "/bin/ruff")
    monkeypatch.setattr(
        source_formatter.subprocess,
        "run",
        lambda command, check: calls.append(command) or subprocess.CompletedProcess(command, 2),
    )
    assert not SourceFormatter().format([Path(f"m{index}.py") for index in range(900)])
    assert len(calls) == 1
