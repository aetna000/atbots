import threading

import pytest

from atbots.platform.components import Components
from atbots.platform.store import AgentStore, StoreError


def test_component_versions_are_actual_and_upgrades_are_allowlisted(tmp_path):
    manager = Components(AgentStore(tmp_path))
    result = manager.inspect()
    assert {row["package"] for row in result["components"]} == {
        "atbots",
        "atmem",
        "atsys",
        "atflows",
    }
    assert next(r for r in result["components"] if r["package"] == "atmem")["installed"]
    for package, target, confirmed in (
        ("evil", "1.0", True),
        ("atmem", "3.0.0", True),
        ("atmem", "2.3.10;echo", True),
        ("atmem", "2.3.10", False),
    ):
        with pytest.raises(StoreError):
            manager.upgrade(package, target, confirmed)


def test_upgrade_cannot_break_atmem_companion_pin(tmp_path):
    manager = Components(AgentStore(tmp_path))
    with pytest.raises(StoreError, match="compatibility pin"):
        manager.upgrade("atflows", "0.2.0", True)


def test_upgrade_requires_idle_then_fixed_pip_argv_and_restart(tmp_path, monkeypatch):
    store = AgentStore(tmp_path)
    store.create("coder")
    prepared = []
    manager = Components(store, prepare=lambda: prepared.append(True))
    with pytest.raises(StoreError, match="Pause"):
        manager.upgrade("atmem", "2.3.10", True)
    store.configure("coder", expected_revision=1, state="paused")
    commands = []
    finished = threading.Event()

    def run(argv, **kwargs):
        commands.append(argv)
        assert kwargs.get("shell") is None
        if argv[-1] == "check":
            finished.set()
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr("atbots.platform.components.subprocess.run", run)
    manager.upgrade("atmem", "2.3.10", True)
    assert finished.wait(3)
    with manager.lock:
        pass
    assert prepared == [True]
    assert commands[0][1:] == ["-m", "pip", "install", "--upgrade", "atmem==2.3.10"]
    assert commands[1][1:] == ["-m", "pip", "check"]
    assert manager.inspect()["maintenance"]["restart_required"]


def test_unfinished_supervision_blocks_upgrade_without_installing(
    tmp_path, monkeypatch
):
    from atbots.platform.integrations import Delegations

    store = AgentStore(tmp_path)
    store.create("coder")
    store.configure("coder", expected_revision=1, state="paused")
    Delegations(store).record("coder", "http://127.0.0.1:4310", {"id": "task-fixture"})
    monkeypatch.setattr(
        "atbots.platform.components.AtSysClient.status",
        lambda self, identity: {"status": "running"},
    )
    monkeypatch.setattr(
        "atbots.platform.components.subprocess.run",
        lambda *a, **k: pytest.fail("Never install over running supervision"),
    )
    with pytest.raises(StoreError, match="Complete or stop"):
        Components(store).upgrade("atmem", "2.3.10", True)
