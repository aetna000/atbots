from __future__ import annotations

import json

import pytest
from pydantic import ValidationError
from pydantic_ai.models.test import TestModel

from atbots.cli import main
from atbots.platform.control import ControlPlan, ControlRoom
from atbots.platform.models import ModelBinding
from atbots.platform.store import AgentStore, StoreError


@pytest.fixture
def store(tmp_path):
    return AgentStore(tmp_path / "platform")


def test_native_intent_and_separate_approval(store):
    model = TestModel(
        custom_output_text=json.dumps({"action": "create", "name": "researcher"})
    )
    room = ControlRoom(store, model=model)
    plan = room.plan("Create a researcher")
    proposal = room.dispatch(plan)
    assert [a.name for a in store.list()] == ["control-room"]
    result = room.approve(proposal["approval_required"])
    assert result["applied"]["name"] == "researcher"
    with pytest.raises(StoreError, match="already used"):
        room.approve(proposal["approval_required"])


def test_registry_passes_metadata_not_agent_instructions_to_planner(store):
    from atbots.platform.session import TurnResult

    captured = []

    class Planner:
        def chat(self, prompt):
            captured.append(json.loads(prompt))
            return TurnResult(
                "control-room", "", "fixture", 1, 1, 1, "fixture", {"action": "list"}
            )

    def factory(*args, **kwargs):
        return Planner()

    store.create("researcher", instructions="UNTRUSTED AGENT INSTRUCTION")
    room = ControlRoom(store, session_factory=factory)
    assert room.plan("List my agents").action == "list"
    assert "UNTRUSTED AGENT INSTRUCTION" not in json.dumps(captured)


def test_read_only_plan_cannot_carry_mutation_fields():
    with pytest.raises(ValidationError):
        ControlPlan(action="inspect", name="researcher", state="retired")
    with pytest.raises(ValidationError):
        ControlPlan(action="configure", name="researcher")
    with pytest.raises(ValidationError):
        ControlPlan(action="ask", name="control-room", message="recurse")
    with pytest.raises(ValidationError):
        ControlPlan(action="run_shell", message="anything")


def test_approval_expiry_stale_configuration_and_rejection(store):
    now = [0.0]
    room = ControlRoom(store, model=TestModel(), clock=lambda: now[0])
    store.create("researcher")
    proposal = room.dispatch(
        ControlPlan(action="configure", name="researcher", state="paused")
    )
    store.configure("researcher", expected_revision=1, instructions="Changed")
    with pytest.raises(StoreError, match="changed"):
        room.approve(proposal["approval_required"])
    proposal = room.dispatch(
        ControlPlan(action="configure", name="researcher", state="paused")
    )
    now[0] = 301
    with pytest.raises(StoreError, match="expired"):
        room.approve(proposal["approval_required"])
    proposal = room.dispatch(ControlPlan(action="create", name="twitter"))
    room.reject(proposal["approval_required"])
    with pytest.raises(StoreError):
        room.approve(proposal["approval_required"])
    assert store.get("researcher").state == "active"


def test_inspect_and_clarify_do_not_change_agent(store):
    room = ControlRoom(store, model=TestModel())
    old = store.create("researcher")
    result = room.dispatch(ControlPlan(action="inspect", name="researcher"))
    assert result["agent"]["revision"] == 1
    assert room.dispatch(ControlPlan(action="clarify", message="Which agent?"))[
        "question"
    ]
    assert store.get("researcher") == old


def test_cli_create_show_configure_and_isolated_default_root(tmp_path, capsys):
    root = str(tmp_path / "platform")
    assert (
        main(
            ["--root", root, "agents", "create", "researcher", "--model", "local-model"]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["binding"]["model"] == "local-model"
    assert main(["--root", root, "agents", "show", "researcher"]) == 0
    assert json.loads(capsys.readouterr().out)["name"] == "researcher"
    assert (
        main(
            [
                "--root",
                root,
                "agents",
                "configure",
                "researcher",
                "--revision",
                "1",
                "--state",
                "paused",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["state"] == "paused"
    assert (
        main(
            [
                "--root",
                root,
                "agents",
                "configure",
                "researcher",
                "--revision",
                "1",
                "--state",
                "active",
            ]
        )
        == 2
    )
    assert "changed" in capsys.readouterr().err


def test_cli_new_does_not_call_model_or_start_background_work(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert main(["--root", str(tmp_path), "--new", "twitter"]) == 0
    assert "Created twitter" in capsys.readouterr().out
    assert AgentStore(tmp_path).receipts("twitter") == []


def test_cli_remote_needs_explicit_grant_and_redacts_validation(tmp_path, capsys):
    root = str(tmp_path / "platform")
    args = ["--root", root, "agents", "create", "researcher", "--provider", "chatgpt"]
    assert main(args) == 2
    assert AgentStore(root).list() == []
    assert main([*args, "--allow-remote", "--model", "my-model"]) == 0
    assert AgentStore(root).get("researcher").remote_allowed
    capsys.readouterr()
    assert (
        main(
            [
                "--root",
                root,
                "agents",
                "create",
                "other",
                "--api-key-env",
                "sk-fake-secret",
            ]
        )
        == 2
    )
    assert "sk-fake-secret" not in capsys.readouterr().err


def test_agent_question_dispatch_does_not_mutate_config(store):
    from atbots.platform.session import AgentSession

    def factory(store, name, **kwargs):
        return AgentSession(
            store, name, model=TestModel(custom_output_text="Agent answer")
        )

    room = ControlRoom(store, session_factory=factory)
    before = store.create("researcher")
    result = room.dispatch(
        ControlPlan(action="ask", name="researcher", message="What do you think?")
    )
    assert result["speaker"] == "researcher" and result["answer"] == "Agent answer"
    assert store.get("researcher") == before


def test_remote_control_proposal_requires_approval_and_binding_grant(store):
    room = ControlRoom(store, model=TestModel())
    plan = ControlPlan(
        action="create",
        name="researcher",
        binding=ModelBinding(kind="chatgpt", egress_class="remote"),
    )
    identity = room.dispatch(plan)["approval_required"]
    with pytest.raises(ValidationError):
        room.approve(identity)
    assert len(store.list()) == 1
