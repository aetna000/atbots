import json

import pytest
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel

from atbots.platform.control import ControlRoom
from atbots.platform.environment import (
    AgentEnvironment,
    configure_supervision,
    supervision_profile,
)
from atbots.platform.memory import AtMemMemory, MemoryContext, MemoryPolicyError
from atbots.platform.session import AgentSession
from atbots.platform.store import AgentStore


def test_native_environment_and_builtin_atsys_with_no_extra_install(tmp_path):
    store = AgentStore(tmp_path)
    store.create("coder")
    calls = 0

    def model(messages, info):
        nonlocal calls
        calls += 1
        assert "persistent AtBots agent" in info.instructions
        # The host manifest is JSON: Windows backslashes must stay escaped.
        assert (
            json.dumps(str(store.workspace("coder") / "files"), ensure_ascii=False)
            in info.instructions
        )
        if calls == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart("inspect_environment", {}),
                    ToolCallPart("available_skills", {}),
                    ToolCallPart("load_atsys_skill", {}),
                ]
            )
        assert "AtMem" in str(messages)
        assert "atsys" in str(messages).lower()
        return ModelResponse(parts=[TextPart("Environment checked")])

    session = AgentSession(store, "coder", model=FunctionModel(model))
    assert (
        session.chat("What tools and workspace do you actually have?").text
        == "Environment checked"
    )
    assert calls == 2
    result = session.environment.request_supervision("Build a project")
    assert result["status"] == "setup_required" and result["started"] is False


def test_private_canaries_never_enter_control_model(tmp_path):
    store = AgentStore(tmp_path)
    for name, fact in (
        ("writer", "I prefer cobalt notebooks"),
        ("coder", "I prefer violet keyboards"),
    ):
        store.create(name)
        AtMemMemory(store, name).remember(fact)
    writer, coder = (AtMemMemory(store, n) for n in ("writer", "coder"))
    assert (
        "cobalt"
        in AgentEnvironment(store, "writer", writer).search_memory("notebooks")[
            "evidence"
        ]
    )
    assert (
        "cobalt"
        not in AgentEnvironment(store, "coder", coder).search_memory("notebooks")[
            "evidence"
        ]
    )
    with pytest.raises(MemoryPolicyError, match="forbidden"):
        coder.confirm(MemoryContext(shared=(("writer", "fake"),)), "test")

    def model(messages, info):
        content = str(messages) + str(info.instructions)
        assert "cobalt" not in content and "violet" not in content
        return ModelResponse(parts=[TextPart('{"action":"list"}')])

    room = ControlRoom(store, model=FunctionModel(model))
    room.dispatch(room.plan("List my agents"))
    assert room.session.memory is None
    assert room.session.environment.tools() == []


def test_agent_remember_is_a_proposal_not_an_authorized_write(tmp_path):
    store = AgentStore(tmp_path)
    store.create("coder")
    memory = AtMemMemory(store, "coder")
    env = AgentEnvironment(store, "coder", memory)
    result = env.request_remember("I prefer concise reports")
    assert result["saved"] is False and not memory.inspect()
    ControlRoom(store, model=TestModel()).approve(result["approval_required"])
    assert "concise" in env.search_memory("reports")["evidence"]


def test_supervision_configuration_is_private_and_revision_bound(tmp_path):
    store = AgentStore(tmp_path)
    store.create("coder")
    store.create("writer")
    profile = {
        "worker": "claude",
        "supervisor_provider": "copilot",
        "trusted_local_execution": True,
        "validation_argv": ["python", "-m", "pytest"],
        "success_criteria": ["Tests pass"],
        "stages": ["Implement", "Test"],
        "plan": "Implement the approved objective and test",
    }
    assert configure_supervision(store, "coder", profile)["configured"]
    assert store.get("coder").revision == 2
    assert supervision_profile(store, "writer") is None
    assert supervision_profile(store, "coder")["worker"] == "claude"
    result = AgentEnvironment(
        store, "coder", AtMemMemory(store, "coder")
    ).request_supervision("Create an output")
    assert result["started"] is False
    assert result["approval_required"]
    assert "output" not in json.dumps(
        AgentEnvironment(
            store, "writer", AtMemMemory(store, "writer")
        ).supervision_tasks()
    )


def test_private_supervision_profile_survives_scoped_state_export(tmp_path):
    from cryptography.fernet import Fernet

    from atbots.platform.deployment import pack_state, unpack_state

    store = AgentStore(tmp_path / "source")
    for name in ("coder", "writer"):
        store.create(name)
        configure_supervision(
            store,
            name,
            {
                "validation_argv": ["python", "-m", "pytest"],
                "success_criteria": [name + " tests pass"],
                "stages": ["Test"],
                "plan": "Validate outputs",
            },
        )
    key = Fernet.generate_key()
    runtime = store.workspace("coder") / "atsys-state"
    runtime.mkdir()
    (runtime / "must-not-export.txt").write_text("Upstream execution-owner state")
    payload = pack_state(store, "coder", key)
    destination = tmp_path / "restored"
    unpack_state(payload, destination, key)
    restored = AgentStore(destination)
    assert [a.name for a in restored.list()] == ["coder"]
    assert not (restored.workspace("coder") / "atsys-state").exists()
    assert supervision_profile(restored, "coder")["success_criteria"] == [
        "coder tests pass"
    ]


def test_agent_task_reports_and_control_are_own_scope_only(tmp_path, monkeypatch):
    from atbots.platform.integrations import AtSysClient, Delegations
    from atbots.platform.jobs import Operations

    store = AgentStore(tmp_path)
    for name in ("coder", "writer"):
        store.create(name)
        Delegations(store).record(name, "http://127.0.0.1:4311", {"id": "task-" + name})
    env = AgentEnvironment(store, "coder", AtMemMemory(store, "coder"))
    calls = []

    def report(self, task_id):
        calls.append(task_id)
        raise RuntimeError("Service is stopped")

    monkeypatch.setattr(AtSysClient, "report", report)
    monkeypatch.setattr(
        "atbots.platform.supervision_service.private_report",
        lambda store, name, task_id: {
            "status": "completed",
            "workflowAccepted": True,
            "digest": "recorded-digest",
            "markdown": "Verified output",
        },
    )
    assert env.supervision_report("task-writer")["status"] == "not_found"
    assert (
        env.request_supervision_action("task-writer", "stop")["status"] == "not_found"
    )
    assert calls == [] and not Operations(store).pending_approvals()
    own = env.supervision_report("task-coder")
    assert own["workflow_accepted"] is True and own["digest"] == "recorded-digest"
    assert calls == ["task-coder"]
    proposal = env.request_supervision_action("task-coder", "pause")
    assert proposal["applied"] is False and proposal["approval_required"]
    assert len(Operations(store).pending_approvals()) == 1
