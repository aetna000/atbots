import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from atbots.platform.desktop import _live, open_desktop
from atbots.platform.store import AgentStore


def test_default_launch_opens_ui_not_model_chat(tmp_path, monkeypatch):
    from atbots.cli import main

    opened = []
    monkeypatch.setattr(
        "atbots.platform.desktop.open_desktop",
        lambda store, **kwargs: opened.append(store.root),
    )
    assert main(["--root", str(tmp_path)]) == 0
    assert opened == [tmp_path]


def test_real_desktop_private_reconnect_and_no_duplicate_runner(tmp_path, monkeypatch):
    root = tmp_path / "isolated-desktop"
    store = AgentStore(root)
    environment = dict(
        os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src")
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "atbots.platform.desktop", "--root", str(root)],
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 15
        value = None
        while time.monotonic() < deadline:
            value = _live(store)
            if value:
                break
            assert process.poll() is None
            time.sleep(0.1)
        assert value and value["pid"] == process.pid
        if os.name != "nt":
            assert (root / "desktop.json").stat().st_mode & 0o077 == 0
        opened = []
        monkeypatch.setattr(
            "atbots.platform.desktop.webbrowser.open",
            lambda address: opened.append(address) or True,
        )
        monkeypatch.setattr(
            "atbots.platform.desktop.subprocess.Popen",
            lambda *a, **k: pytest.fail("Reopening must not spawn a second desktop"),
        )
        open_desktop(store)
        assert opened == [f"http://127.0.0.1:{value['port']}#token={value['token']}"]
        assert json.loads((root / "desktop.json").read_text())["pid"] == process.pid
        assert (
            store.receipts("control-room") == []
        )  # No paid or local inference while idle.
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_scheduler_transient_failure_recovers_without_job_replay(tmp_path, monkeypatch):
    from atbots.platform.desktop import run

    ready = __import__("threading").Event()
    attempts = []
    observed = {}

    def serve(self, *, stop, report):
        attempts.append(True)
        if len(attempts) < 3:
            raise OSError("transient setup issue with private detail")
        report()
        ready.set()

    class Server:
        server_port = 43567

        def serve_forever(self):
            assert ready.wait(8)

        def server_close(self):
            pass

    def server(store, **kwargs):
        observed.update(kwargs)
        return Server(), "fixture-local-token"

    monkeypatch.setattr("atbots.platform.web.create_server", server)
    monkeypatch.setattr("atbots.platform.scheduler.Scheduler.serve", serve)
    assert run(AgentStore(tmp_path)) is False
    assert len(attempts) == 3
    assert observed["desktop_status"]["scheduler"] == "ready"
    assert "private detail" not in json.dumps(observed["desktop_status"])
    assert not (tmp_path / "desktop.json").exists()
