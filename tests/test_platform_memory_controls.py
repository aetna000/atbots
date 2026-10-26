import pytest
from pydantic_ai.models.test import TestModel

from atbots.platform.control import ControlPlan, ControlRoom
from atbots.platform.memory import AtMemMemory, MemoryPolicyError
from atbots.platform.store import AgentStore


def test_correct_forget_and_cross_scope_denial(tmp_path):
    store = AgentStore(tmp_path)
    store.create("researcher")
    store.create("other")
    memory = AtMemMemory(store, "researcher")
    record = memory.remember("My favorite color is blue")["record_ids"][0]
    with pytest.raises(MemoryPolicyError):
        AtMemMemory(store, "other").forget(record)
    result = memory.correct(record, "My favorite color is green")
    new = result["record"]["id"]
    assert "green" in memory.context("favorite color", egress="local").text
    assert memory.inspect(record)[0]["status"] == "superseded"
    assert memory.forget(new)["receipt"]["receipt_sha256"]
    assert "green" not in memory.context("favorite color", egress="local").text


def test_sharing_is_directional_live_and_revocable(tmp_path):
    store = AgentStore(tmp_path)
    store.create("researcher")
    store.create("other")
    a, b = AtMemMemory(store, "researcher"), AtMemMemory(store, "other")
    a.remember("I prefer concise technical answers")
    assert not b.context("concise technical answers", egress="local").text
    store.share_memory("researcher", "other", enabled=True)
    context = b.context("concise technical answers", egress="local")
    assert "Shared by researcher" in context.text
    assert b.confirm(context, "run-shared")
    assert store.shared_sources("researcher") == []
    store.share_memory("researcher", "other", enabled=False)
    assert not b.context("concise technical answers", egress="local").text
    with pytest.raises(MemoryPolicyError, match="revoked"):
        b.confirm(context, "run-revoked")


def test_automatic_rules_capture_not_unverified_agent_output(tmp_path):
    store = AgentStore(tmp_path)
    store.create("researcher")
    memory = AtMemMemory(store, "researcher")
    assert (
        memory.capture_user("I prefer concise technical answers")["captured_records"]
        == 1
    )
    assert memory.capture_user("What do I prefer?")["captured_records"] == 0
    assert len(memory.inspect()) == 1


def test_control_room_memory_mutations_require_approval(tmp_path):
    store = AgentStore(tmp_path)
    store.create("researcher")
    room = ControlRoom(store, model=TestModel())
    proposal = room.dispatch(
        ControlPlan(
            action="memory_remember",
            name="researcher",
            message="I prefer concise technical answers",
        )
    )
    assert AtMemMemory(store, "researcher").inspect() == []
    assert (
        room.approve(proposal["approval_required"])["memory_result"]["decision"]
        == "active"
    )
    records = room.dispatch(ControlPlan(action="memory_inspect", name="researcher"))[
        "memories"
    ]
    proposal = room.dispatch(
        ControlPlan(
            action="memory_forget", name="researcher", record_id=records[0]["id"]
        )
    )
    assert room.approve(proposal["approval_required"])["memory_result"]["deleted"]
