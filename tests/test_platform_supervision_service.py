import hashlib

import pytest
from pydantic_ai.models.test import TestModel

from atbots.platform.control import ControlRoom
from atbots.platform.environment import AgentEnvironment, configure_supervision
from atbots.platform.integrations import AtSysClient
from atbots.platform.memory import AtMemMemory
from atbots.platform.store import AgentStore, StoreError
from atbots.platform.supervision_service import start_private


def test_private_setup_uses_only_agent_owned_state_and_upstream_commands(
    tmp_path, monkeypatch
):
    store = AgentStore(tmp_path)
    store.create("coder")
    root = store.workspace("coder") / "atsys-state"
    commands = []

    def run(argv, **kwargs):
        commands.append(argv)
        assert kwargs["env"]["ATSYS_DATA_DIR"] == str(root)
        assert "ATSYS_PORT" not in kwargs["env"]
        return type(
            "Result", (), {"returncode": 0, "stdout": "http://127.0.0.1:4311"}
        )()

    monkeypatch.setattr(
        "atbots.platform.supervision_service.SUPERVISION_SUPPORTED", True
    )
    monkeypatch.setattr("atbots.platform.supervision_service.subprocess.run", run)
    monkeypatch.setattr("atbots.platform.supervision_service._alive", lambda pid: True)
    monkeypatch.setattr(
        AtSysClient,
        "health",
        lambda self: {"instanceId": hashlib.sha256(str(root).encode()).hexdigest()},
    )
    monkeypatch.setattr(
        AtSysClient,
        "request",
        lambda *a, **k: {"daemonHealthy": True, "daemon": {"providerProtocol": 1}},
    )
    value = start_private(store, "coder", confirmed=True)
    assert value["status"] == "ready" and value["task_started"] is False
    assert commands[0][1:] == ["-m", "atsys", "ui", "--no-open"]
    assert commands[1][1:] == ["-m", "atsys", "service", "start"]


def test_stale_watchdog_refusal_leaves_approval_pending(tmp_path, monkeypatch):
    store = AgentStore(tmp_path)
    store.create("coder")
    configure_supervision(
        store,
        "coder",
        {
            "validation_argv": ["python", "-m", "pytest"],
            "success_criteria": ["Tests pass"],
            "stages": ["Test"],
            "plan": "Validate this objective",
        },
    )
    value = AgentEnvironment(
        store, "coder", AtMemMemory(store, "coder")
    ).request_supervision("Create a tested artifact")
    monkeypatch.setattr(AtSysClient, "health", lambda self: {"version": "0.3.0b4"})
    calls = []

    def request(self, path, **kwargs):
        calls.append(path)
        return {"daemonHealthy": True, "daemon": {"providerProtocol": 0}}

    monkeypatch.setattr(AtSysClient, "request", request)
    room = ControlRoom(store, model=TestModel())
    with pytest.raises(StoreError, match="watchdog"):
        room.approve(value["approval_required"])
    assert room.operations.pending_approvals()[0]["state"] == "pending"
    assert calls == ["/api/operations"]


def test_git_initialization_is_explicit_and_never_uses_ambient_git_dir(
    tmp_path, monkeypatch
):
    store = AgentStore(tmp_path)
    store.create("coder")
    monkeypatch.setenv("GIT_DIR", "/outside-must-not-be-used")
    monkeypatch.setattr(
        "atbots.platform.supervision_service.SUPERVISION_SUPPORTED", True
    )
    commands = []

    def run(argv, **kwargs):
        commands.append((argv, kwargs))
        assert "GIT_DIR" not in kwargs["env"]
        if argv[0] == "git":
            assert "GIT_DIR" not in kwargs["env"]
            assert argv[-1] == str(store.workspace("coder") / "files")
            assert kwargs["env"]["GIT_CONFIG_GLOBAL"] == __import__("os").devnull
            return None
        raise OSError("Intentional service-start failure after Git preflight")

    monkeypatch.setattr("atbots.platform.supervision_service.subprocess.run", run)
    with pytest.raises(StoreError, match="setup needs attention"):
        start_private(store, "coder", confirmed=True, initialize_git=True)
    assert commands[0][0][0] == "git"


def test_stop_private_refuses_active_tasks_without_signalling_any_process(
    tmp_path, monkeypatch
):
    from atbots.platform.supervision_service import stop_private

    store = AgentStore(tmp_path)
    store.create("coder")
    root = store.workspace("coder") / "atsys-state"
    root.mkdir()
    (root / "dashboard.json").write_text("{}")
    monkeypatch.setattr(
        "atbots.platform.supervision_service.SUPERVISION_SUPPORTED", True
    )
    monkeypatch.setattr(
        "atbots.platform.supervision_service.private_state",
        lambda *args: {
            "record": {"pid": None},
            "service": {},
            "tasks": [{"status": "running"}],
            "daemon": None,
        },
    )
    monkeypatch.setattr(
        "atbots.platform.supervision_service.os.kill",
        lambda *args: pytest.fail("No signal is allowed for active work"),
    )
    with pytest.raises(StoreError, match="Finish or stop"):
        stop_private(store, "coder", confirmed=True)


def test_stop_private_verifies_all_targets_before_any_signal(tmp_path, monkeypatch):
    from atbots.platform.supervision_service import stop_private

    store = AgentStore(tmp_path)
    store.create("coder")
    root = store.workspace("coder") / "atsys-state"
    root.mkdir()
    (root / "dashboard.json").write_text("{}")
    monkeypatch.setattr(
        "atbots.platform.supervision_service.SUPERVISION_SUPPORTED", True
    )
    monkeypatch.setattr("atbots.platform.supervision_service._alive", lambda pid: False)
    monkeypatch.setattr(
        "atbots.platform.supervision_service.private_state",
        lambda *args: {
            "record": {"pid": 11111},
            "service": {},
            "tasks": [{"status": "completed"}],
            "daemon": {"pid": 22222},
        },
    )

    def owned(pid, root, **kwargs):
        if pid == 22222:
            raise StoreError("Foreign process refused")
        return True

    monkeypatch.setattr("atbots.platform.supervision_service._owned_pid", owned)
    monkeypatch.setattr(
        "atbots.platform.supervision_service.os.kill",
        lambda *args: pytest.fail("Do not partially stop unverified targets"),
    )
    with pytest.raises(StoreError, match="Foreign"):
        stop_private(store, "coder", confirmed=True)
