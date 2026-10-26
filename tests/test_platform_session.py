from __future__ import annotations

import asyncio

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel

from atbots.platform.models import RunLimits
from atbots.platform.session import AgentSession, SessionError
from atbots.platform.store import AgentStore, StoreError


@pytest.fixture
def store(tmp_path):
    value = AgentStore(tmp_path / "platform")
    value.create("researcher")
    value.create("twitter")
    return value


def test_native_agent_history_survives_restart(store):
    lengths = []

    def reply(messages, info):
        lengths.append(len(messages))
        return ModelResponse(parts=[TextPart("Native response")])

    session = AgentSession(store, "researcher", model=FunctionModel(reply))
    assert isinstance(session.agent, Agent)
    assert session.chat("First message").text == "Native response"
    assert (
        AgentSession(AgentStore(store.root), "researcher", model=FunctionModel(reply))
        .chat("Second")
        .text
        == "Native response"
    )
    assert lengths == [1, 3]
    assert store.history("researcher")[0] == 2
    assert store.history("twitter") == (0, b"[]")
    assert store.receipts("researcher")[-1]["cost"] is None
    assert not store.receipts("researcher")[-1]["objective_verified"]


def test_native_pydantic_tool_dispatch_not_legacy_loop(store):
    def local_fact() -> str:
        """Return a fixture fact."""
        return "fixture-137"

    session = AgentSession(store, "researcher", model=TestModel(), tools=(local_fact,))
    result = session.chat("Use the fixture tool")
    assert "fixture-137" in result.text
    assert result.requests == 2


def test_failure_is_redacted_not_persisted_as_success(store):
    def fail(messages, info):
        raise RuntimeError("secret-token-provider-body")

    session = AgentSession(store, "researcher", model=FunctionModel(fail))
    with pytest.raises(SessionError) as error:
        session.chat("Private prompt")
    assert "secret-token" not in str(error.value)
    assert store.history("researcher") == (0, b"[]")
    assert store.receipts("researcher")[0]["failure_type"] == "RuntimeError"
    assert "secret-token" not in str(store.receipts("researcher"))


def test_request_budget_stops_native_loop(store):
    store.configure(
        "researcher", expected_revision=1, limits=RunLimits(requests=1).model_dump()
    )

    def repeat(messages, info):
        return ModelResponse(parts=[ToolCallPart("local_fact", {})])

    def local_fact() -> str:
        return "fixture"

    with pytest.raises(SessionError):
        AgentSession(
            store, "researcher", model=FunctionModel(repeat), tools=(local_fact,)
        ).chat("Go")
    assert store.receipts("researcher")[-1]["failure_type"] == "UsageLimitExceeded"


def test_timeout_and_paused_config_changes(store):
    store.configure(
        "researcher",
        expected_revision=1,
        limits=RunLimits(timeout_seconds=1).model_dump(),
    )

    async def slow(messages, info):
        await asyncio.sleep(2)
        return ModelResponse(parts=[TextPart("late")])

    with pytest.raises(SessionError):
        AgentSession(store, "researcher", model=FunctionModel(slow)).chat("Go")
    session = AgentSession(store, "researcher", model=TestModel())
    store.configure("researcher", expected_revision=2, state="paused")
    with pytest.raises(StoreError, match="paused"):
        session.chat("No")


def test_stale_session_must_reopen_and_busy_is_explicit(store):
    session = AgentSession(store, "researcher", model=TestModel())
    store.configure("researcher", expected_revision=1, instructions="Changed")
    with pytest.raises(StoreError, match="reopen"):
        session.chat("No")
    fresh = AgentSession(store, "researcher", model=TestModel())
    with store.turn_lock("researcher"), pytest.raises(StoreError, match="busy"):
        fresh.chat("No")


def test_named_model_does_not_fall_back_when_unreachable(store, monkeypatch):
    from contextlib import asynccontextmanager

    import atbots.platform.session as module

    @asynccontextmanager
    async def unavailable(binding):
        raise RuntimeError("unavailable provider; secret")
        yield

    monkeypatch.setattr(module, "configured_model", unavailable)
    with pytest.raises(SessionError):
        AgentSession(store, "researcher").chat("Hello")
    assert store.receipts("researcher")[-1]["status"] == "failed"


def test_sensitive_input_cannot_use_remote_model(store):
    from atbots.platform.models import ModelBinding

    store.configure(
        "researcher",
        expected_revision=1,
        binding=ModelBinding(kind="chatgpt", egress_class="remote").model_dump(),
        remote_allowed=True,
    )
    with pytest.raises(StoreError, match="Sensitive/restricted"):
        AgentSession(store, "researcher", model=TestModel()).chat(
            "Private content", sensitivity="restricted"
        )
    assert store.receipts("researcher") == []
