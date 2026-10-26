from __future__ import annotations

import pytest
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel

from atbots.platform.memory import AtMemMemory, MemoryContext, MemoryPolicyError
from atbots.platform.session import AgentSession, SessionError
from atbots.platform.store import AgentStore


@pytest.fixture
def store(tmp_path):
    value = AgentStore(tmp_path / "platform")
    value.create("researcher")
    value.create("twitter")
    return value


def test_real_atmem_admission_scope_recall_and_exposure(store):
    memory = AtMemMemory(store, "researcher")
    admission = memory.remember("I prefer concise technical answers")
    assert admission["decision"] == "active"
    context = memory.context("concise technical answers", egress="local")
    assert "concise technical answers" in context.text
    assert memory.confirm(context, "run-fixture")
    assert (
        AtMemMemory(store, "twitter")
        .context("concise technical answers", egress="local")
        .text
        == ""
    )
    records = memory.gateway.inspect_records()
    assert len(records) == 1
    assert records[0]["content"] == "I prefer concise technical answers"
    assert (
        memory.remember("I prefer concise technical answers")["decision"] == "duplicate"
    )


def test_native_session_receives_applicable_memory_and_records_receipt(store):
    AtMemMemory(store, "researcher").remember("I prefer concise technical answers")

    def reply(messages, info):
        assert "concise technical answers" in info.instructions
        return ModelResponse(parts=[TextPart("I will keep this concise.")])

    result = AgentSession(store, "researcher", model=FunctionModel(reply)).chat(
        "concise technical answers"
    )
    assert result.memory_receipt
    assert store.receipts("researcher")[-1]["memory_receipt"] == result.memory_receipt


def test_explicit_memory_command_and_exclusion(store):
    session = AgentSession(
        store, "researcher", model=TestModel(custom_output_text="Noted")
    )
    session.chat("remember: I prefer concise technical answers")
    memory = AtMemMemory(store, "researcher")
    assert len(memory.gateway.inspect_records()) == 1
    assert (
        memory.remember("Do not store this: my meeting is tomorrow")["decision"]
        == "rejected"
    )
    assert len(memory.gateway.inspect_records()) == 1


def test_recognizable_secret_never_reaches_model_history_or_memory(store):
    calls = []

    def reply(messages, info):
        calls.append(messages)
        return ModelResponse(parts=[TextPart("Unexpected")])

    session = AgentSession(store, "researcher", model=FunctionModel(reply))
    with pytest.raises(MemoryPolicyError):
        session.chat("My password is fixture-only-not-real")
    assert not calls
    assert store.history("researcher") == (0, b"[]")
    assert not (store.workspace("researcher") / "memory.db").exists()


def test_memory_failure_is_not_claimed_saved_or_silently_ignored(store):
    class BrokenMemory:
        def context(self, query, *, egress):
            raise OSError("unavailable")

    with pytest.raises(SessionError):
        AgentSession(
            store, "researcher", model=TestModel(), memory=BrokenMemory()
        ).chat("Hello")
    assert store.receipts("researcher")[-1]["status"] == "failed"
    assert store.history("researcher") == (0, b"[]")


def test_substitute_port_needs_no_objective_or_tool_rewrite(store):
    class OtherMemory:
        def context(self, query, *, egress):
            return MemoryContext("Fixture preference: concise")

        def confirm(self, context, run_id):
            return "fixture-receipt"

    def reply(messages, info):
        assert "Fixture preference: concise" in info.instructions
        return ModelResponse(parts=[TextPart("Concise reply")])

    result = AgentSession(
        store, "researcher", model=FunctionModel(reply), memory=OtherMemory()
    ).chat("Hello")
    assert result.memory_receipt == "fixture-receipt"
