"""The chat `#logs` command must not read the whole run.log to show its tail.

``run.log`` is appended to for as long as CowAgent runs and is never rotated.
``CowCliPlugin._cmd_logs`` loaded it with ``readlines()`` and then kept
``all_lines[-num_lines:]`` -- every line ever written was read into memory to
show twenty of them. Unlike the CLI equivalent this runs inside the bot
process, so a long-lived instance gets OOM-killed by its own help command.
"""

import builtins
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import plugins

_old_plugin_path = plugins.instance.current_plugin_path
plugins.instance.current_plugin_path = os.path.join(os.getcwd(), "plugins", "cow_cli")
try:
    from plugins.cow_cli import cow_cli as cow_cli_mod

    CowCliPlugin = plugins.instance.plugins["COW_CLI"]
finally:
    plugins.instance.current_plugin_path = _old_plugin_path


class _RecordingFile:
    """Wraps a file object and counts how much of it the caller actually reads."""

    def __init__(self, inner, record):
        self._inner = inner
        self._record = record

    def readlines(self, *args, **kwargs):
        self._record["readlines"] += 1
        return self._inner.readlines(*args, **kwargs)

    def read(self, *args, **kwargs):
        data = self._inner.read(*args, **kwargs)
        self._record["read_bytes"] += len(data)
        return data

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def __enter__(self):
        self._inner.__enter__()
        return self

    def __exit__(self, *exc):
        return self._inner.__exit__(*exc)


def _write_log(path, line_count):
    # newline="\n" keeps the fixture byte-identical on Windows.
    with builtins.open(str(path), "w", encoding="utf-8", newline="\n") as f:
        for i in range(line_count):
            f.write(f"[INFO] 2026-09-30 00:00:00 - log line number {i}\n")
    return path


def test_logs_command_reads_only_the_tail(tmp_path, monkeypatch):
    """`cow logs` must not pull the entire log into the bot process."""
    log_path = _write_log(tmp_path / "run.log", 20000)
    record = {"readlines": 0, "read_bytes": 0}
    real_open = builtins.open

    def spy_open(file, *args, **kwargs):
        return _RecordingFile(real_open(file, *args, **kwargs), record)

    monkeypatch.setattr(cow_cli_mod, "open", spy_open, raising=False)
    plugin = CowCliPlugin.__new__(CowCliPlugin)
    monkeypatch.setattr(
        CowCliPlugin, "_find_log_file", lambda self: str(log_path)
    )

    out = plugin._cmd_logs("20", None)

    assert "log line number 19999" in out
    assert record["readlines"] == 0, (
        "the whole log was read into memory just to keep the last few lines"
    )
    assert record["read_bytes"] < log_path.stat().st_size // 2, (
        f"read {record['read_bytes']} bytes of a {log_path.stat().st_size} byte log"
    )


def test_tail_lines_returns_the_last_n_lines(tmp_path):
    path = _write_log(tmp_path / "run.log", 5000)
    with builtins.open(str(path), "r", encoding="utf-8") as f:
        expected = f.readlines()[-20:]

    assert cow_cli_mod._tail_lines(str(path), 20) == expected


def test_tail_lines_handles_a_file_smaller_than_the_limit(tmp_path):
    path = _write_log(tmp_path / "run.log", 3)

    tail = cow_cli_mod._tail_lines(str(path), 20)

    assert len(tail) == 3
    assert tail[-1].endswith("log line number 2\n")


def test_tail_lines_handles_an_empty_file(tmp_path):
    path = tmp_path / "run.log"
    path.write_bytes(b"")

    assert cow_cli_mod._tail_lines(str(path), 20) == []
