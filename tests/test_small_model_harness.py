"""The task loop must survive a small model that misbehaves per step."""

from __future__ import annotations

import json

import pytest

from atbots.agent import TaskAgent
from atbots.capabilities import Tool, guard_tool_result
from atbots.config import AtBotConfig
from atbots.domain import ProviderResult
from atbots.providers.ollama_ctx import ContextProvision, context_tag, ensure_context_tag
from atbots.providers.pydantic_ai import strip_reasoning
from atbots.steps import STEP_SCHEMA, TaskStep


class ScriptedProvider:
    """Replays a script of model behaviours, including failures."""

    name = "scripted"
    model = "scripted-model"
    egress_class = "local"

    def __init__(self, script: list[object]) -> None:
        self.script = list(script)
        self.prompts: list[str] = []

    def available(self) -> bool:
        return True

    def complete(self, *, system, prompt, schema=None, output_type=None) -> ProviderResult:
        del system, schema
        assert output_type is TaskStep, "the loop must request a constrained step"
        self.prompts.append(prompt)
        step = self.script.pop(0) if self.script else {"action": "finish", "reason": "done"}
        if isinstance(step, Exception):
            raise step
        return ProviderResult(
            text=json.dumps(step), structured=step, provider=self.name,
            model=self.model, egress_class=self.egress_class,
        )


class StubRuntime:
    def __init__(self, candidates: list[str] | None = None) -> None:
        self.candidates = candidates or []

    def recall(self, query: str):  # noqa: ARG002 - signature parity only
        rows = [type("Row", (), {"content": text, "score": 1.0})() for text in self.candidates]
        return type("Result", (), {"candidates": rows})()


def build(script: list[object], **overrides) -> TaskAgent:
    settings = {"allowed_tools": ["memory_recall"], "memory_path": ":memory:"}
    settings.update(overrides)
    config = AtBotConfig(**settings)
    agent = TaskAgent(config, runtime=StubRuntime(["the user likes cats"]))
    agent.router._providers = [ScriptedProvider(script)]  # noqa: SLF001 - test seam
    return agent


def provider(agent: TaskAgent) -> ScriptedProvider:
    return agent.router._providers[0]  # noqa: SLF001 - test seam


def test_run_survives_consecutive_malformed_decisions() -> None:
    agent = build(
        [
            RuntimeError("model returned prose, not a decision"),
            ValueError("validation failed after retries"),
            {"action": "wander", "reason": "off schema"},
            {"action": "finish", "reason": "recovered", "answer": "the user likes cats"},
        ]
    )
    result = agent.run("what does the user like")
    assert result.status == "completed"
    assert result.answer == "the user likes cats"
    assert sum(1 for row in result.trace if row["action"] == "recover") == 3


def test_model_is_told_its_output_could_not_be_read() -> None:
    agent = build([RuntimeError("boom"), {"action": "finish", "reason": "ok", "answer": "a"}])
    agent.run("objective")
    assert "could not be read" in provider(agent).prompts[1]


def test_hallucinated_tool_name_is_recoverable_and_names_real_tools() -> None:
    agent = build(
        [
            {"action": "tool", "reason": "guessing", "tool": "web_search", "arguments": {}},
            {"action": "finish", "reason": "ok", "answer": "done"},
        ]
    )
    result = agent.run("objective")
    assert result.status == "completed"
    assert "memory_recall" in provider(agent).prompts[1]
    assert "web_search" in provider(agent).prompts[1]


def test_destructive_tool_is_refused_without_ending_the_run() -> None:
    agent = build(
        [
            {"action": "tool", "reason": "try", "tool": "wipe", "arguments": {}},
            {"action": "finish", "reason": "ok", "answer": "done"},
        ],
        allowed_tools=["memory_recall", "wipe"],
    )
    agent.tools.register(
        Tool(name="wipe", description="Delete everything.", input_schema={}, handler=lambda _: None, destructive=True)
    )
    result = agent.run("objective")
    assert result.status == "completed"
    assert any(row["action"] == "recover" and row["status"] == "rejected" for row in result.trace)


def test_tool_exception_becomes_an_observation() -> None:
    agent = build(
        [
            {"action": "tool", "reason": "call", "tool": "flaky", "arguments": {}},
            {"action": "finish", "reason": "ok", "answer": "done"},
        ],
        allowed_tools=["memory_recall", "flaky"],
    )

    def explode(_: dict) -> object:
        raise ZeroDivisionError("division by zero")

    agent.tools.register(Tool(name="flaky", description="Fails.", input_schema={}, handler=explode))
    result = agent.run("objective")
    assert result.status == "completed"
    assert "ZeroDivisionError" in provider(agent).prompts[1]


def test_exhausted_budget_returns_a_result_rather_than_raising() -> None:
    # A model that keeps naming tools that do not exist never crashes the run,
    # but it does run out of budget.
    script = [{"action": "tool", "reason": "guess", "tool": "nope", "arguments": {"i": n}} for n in range(9)]
    agent = build(script, max_task_steps=3)
    result = agent.run("objective")
    assert result.status == "step_limit"
    assert result.steps == 3
    assert "step limit" in result.answer


def test_step_limit_answer_reports_the_last_useful_observation() -> None:
    script = [{"action": "tool", "reason": "guess", "tool": "nope", "arguments": {"i": n}} for n in range(9)]
    agent = build(script, max_task_steps=2)
    result = agent.run("what does the user like")
    assert "likes cats" in result.answer


def test_a_provider_that_always_fails_reports_its_own_error() -> None:
    agent = build([RuntimeError("model 'qwen3:4b' not found")] * 10, max_task_steps=8)
    result = agent.run("objective")
    assert result.status == "provider_error"
    assert "not found" in result.answer
    assert result.steps < 8, "a dead provider must not consume the whole budget"


def test_a_transient_provider_failure_still_recovers() -> None:
    agent = build(
        [
            RuntimeError("blip"),
            RuntimeError("blip"),
            {"action": "finish", "reason": "ok", "answer": "recovered"},
        ],
        provider_failure_limit=3,
    )
    result = agent.run("objective")
    assert result.status == "completed"
    assert result.answer == "recovered"


def test_repeated_tool_call_is_not_re_invoked() -> None:
    calls: list[dict] = []
    repeat = {"action": "tool", "reason": "again", "tool": "counter", "arguments": {"n": 1}}
    agent = build(
        [dict(repeat), dict(repeat), {"action": "finish", "reason": "ok", "answer": "done"}],
        allowed_tools=["memory_recall", "counter"],
    )
    agent.tools.register(
        Tool(
            name="counter",
            description="Counts calls.",
            input_schema={"type": "object", "properties": {"n": {"type": "integer"}}},
            handler=lambda arguments: calls.append(arguments) or "counted",
        )
    )
    result = agent.run("objective")
    assert result.status == "completed"
    assert len(calls) == 1
    assert "already called" in provider(agent).prompts[2]


def test_observations_are_truncated_to_the_configured_limit() -> None:
    agent = build(
        [
            {"action": "tool", "reason": "call", "tool": "big", "arguments": {}},
            {"action": "finish", "reason": "ok", "answer": "done"},
        ],
        allowed_tools=["memory_recall", "big"],
        observation_char_limit=200,
    )
    agent.tools.register(
        Tool(name="big", description="Huge.", input_schema={}, handler=lambda _: "x" * 50_000)
    )
    agent.run("objective")
    prompt = provider(agent).prompts[1]
    assert "truncated" in prompt
    assert len(prompt) < 2_000


def test_only_the_recent_observations_are_retained() -> None:
    script = [
        {"action": "tool", "reason": "call", "tool": "echo", "arguments": {"n": index}}
        for index in range(6)
    ]
    script.append({"action": "finish", "reason": "ok", "answer": "done"})
    agent = build(
        script,
        allowed_tools=["memory_recall", "echo"],
        max_task_steps=10,
        observation_window=3,
    )
    agent.tools.register(
        Tool(
            name="echo",
            description="Echoes.",
            input_schema={"type": "object", "properties": {"n": {"type": "integer"}}},
            handler=lambda arguments: f"echo-{arguments['n']}",
        )
    )
    agent.run("objective")
    final = provider(agent).prompts[-1]
    assert "earlier observations omitted" in final
    assert "echo-5" in final
    assert "echo-0" not in final


def test_prompt_lists_tools_compactly() -> None:
    agent = build([{"action": "finish", "reason": "ok", "answer": "done"}])
    agent.run("objective")
    assert "- memory_recall(query):" in provider(agent).prompts[0]


def test_empty_objective_still_rejected() -> None:
    agent = build([])
    with pytest.raises(ValueError, match="objective is required"):
        agent.run("   ")


def test_step_schema_matches_the_output_type() -> None:
    assert STEP_SCHEMA["title"] == "AtBotTaskStep"
    assert set(STEP_SCHEMA["properties"]) == set(TaskStep.model_fields)


def test_guard_tool_result_default_suits_a_small_window() -> None:
    assert len(guard_tool_result("y" * 50_000)) < 2_100


def test_strip_reasoning_removes_inline_blocks() -> None:
    assert strip_reasoning('<think>hmm</think>{"action":"finish"}') == '{"action":"finish"}'
    assert strip_reasoning('{"action":"finish"}') == '{"action":"finish"}'


def test_context_tag_naming_and_opt_out() -> None:
    assert context_tag("qwen3:4b", 8192) == "qwen3:4b-atbots-ctx8192"
    assert ensure_context_tag(endpoint="http://127.0.0.1:1", model="qwen3:4b", num_ctx=None) == (
        ContextProvision("qwen3:4b", None, False, None)
    )


def test_unreachable_ollama_degrades_instead_of_raising() -> None:
    result = ensure_context_tag(endpoint="http://127.0.0.1:1", model="qwen3:4b", num_ctx=8192)
    assert result.tag == "qwen3:4b"
    assert result.provisioned is False
    assert "not reachable" in (result.reason or "")


def test_a_pinned_derived_tag_is_left_alone() -> None:
    result = ensure_context_tag(
        endpoint="http://127.0.0.1:1", model="qwen3:4b-atbots-ctx16384", num_ctx=16384
    )
    assert result.tag == "qwen3:4b-atbots-ctx16384"


def test_finish_without_trying_a_tool_is_pushed_back_once() -> None:
    agent = build(
        [
            {"action": "finish", "reason": "I know this", "answer": "about 10 GB"},
            {"action": "tool", "reason": "checking", "tool": "disk_free", "arguments": {}},
            {"action": "finish", "reason": "grounded", "answer": "137 GB"},
        ],
        allowed_tools=["memory_recall", "disk_free"],
    )
    agent.tools.register(
        Tool(name="disk_free", description="Free space.", input_schema={}, handler=lambda _: {"free_gb": 137})
    )
    result = agent.run("how much free disk space")
    assert result.answer == "137 GB"
    assert "you finished without using disk_free" in provider(agent).prompts[1]


def test_push_back_happens_at_most_once() -> None:
    agent = build(
        [
            {"action": "finish", "reason": "guessing", "answer": "about 10 GB"},
            {"action": "finish", "reason": "still guessing", "answer": "about 10 GB"},
        ],
        allowed_tools=["memory_recall", "disk_free"],
    )
    agent.tools.register(
        Tool(name="disk_free", description="Free space.", input_schema={}, handler=lambda _: {"free_gb": 137})
    )
    result = agent.run("how much free disk space")
    assert result.status == "completed"
    assert result.steps == 2


def test_no_push_back_when_every_tool_already_succeeded() -> None:
    agent = build([{"action": "finish", "reason": "recalled", "answer": "cats"}])
    result = agent.run("what does the user like")
    assert result.status == "completed"
    assert result.steps == 1


def test_step_rejects_a_tool_action_with_no_tool_named() -> None:
    with pytest.raises(ValueError, match="one of the listed tool names"):
        TaskStep(action="tool", reason="vague", answer="I think it is 10 GB")


def test_step_accepts_a_named_tool_and_a_plain_finish() -> None:
    assert TaskStep(action="tool", reason="r", tool="disk_free").tool == "disk_free"
    assert TaskStep(action="finish", reason="r", answer="a").action == "finish"


def test_a_repeatedly_failing_tool_does_not_consume_the_budget() -> None:
    """A tool that always raises must be caught as repetition, not retried.

    Found by the Tier 2 evals: `seen` was recorded only on the success path, so a
    model that kept calling a broken tool burned every step in the budget.
    """
    calls: list[dict] = []

    def explode(arguments: dict) -> object:
        calls.append(arguments)
        raise RuntimeError("the tool is broken")

    repeat = {"action": "tool", "reason": "retry", "tool": "broken", "arguments": {}}
    agent = build(
        [dict(repeat) for _ in range(8)] + [{"action": "finish", "reason": "gave up", "answer": "could not get it"}],
        allowed_tools=["memory_recall", "broken"],
        max_task_steps=9,
    )
    agent.tools.register(Tool(name="broken", description="Always fails.", input_schema={}, handler=explode))
    result = agent.run("use the broken tool")
    assert result.status == "completed"
    assert len(calls) == 1, f"the failing tool was invoked {len(calls)} times"
    assert "Calling it again will not help" in provider(agent).prompts[2]


def test_a_repeatedly_invented_tool_name_is_caught_as_repetition() -> None:
    invented = {"action": "tool", "reason": "guess", "tool": "web_search", "arguments": {"q": "x"}}
    agent = build(
        [dict(invented), dict(invented), {"action": "finish", "reason": "ok", "answer": "done"}]
    )
    result = agent.run("objective")
    assert result.status == "completed"
    assert "was rejected" in provider(agent).prompts[2]


def test_a_successful_repeat_still_reports_the_earlier_result() -> None:
    repeat = {"action": "tool", "reason": "again", "tool": "echo", "arguments": {"n": 1}}
    agent = build(
        [dict(repeat), dict(repeat), {"action": "finish", "reason": "ok", "answer": "done"}],
        allowed_tools=["memory_recall", "echo"],
    )
    agent.tools.register(
        Tool(
            name="echo",
            description="Echoes.",
            input_schema={"type": "object", "properties": {"n": {"type": "integer"}}},
            handler=lambda arguments: f"echo-{arguments['n']}",
        )
    )
    agent.run("objective")
    assert "already called with these arguments and returned" in provider(agent).prompts[2]


def test_a_failing_tool_is_abandoned_even_when_arguments_vary() -> None:
    """Keying repeats on arguments is not enough on its own.

    A model that varies its arguments on each retry walks straight past the
    repeat index, so a broken tool is also capped by failure count.
    """
    calls: list[dict] = []

    def explode(arguments: dict) -> object:
        calls.append(arguments)
        raise RuntimeError("the tool is broken")

    script = [
        {"action": "tool", "reason": "retry", "tool": "broken", "arguments": {"attempt": n}}
        for n in range(8)
    ]
    script.append({"action": "finish", "reason": "gave up", "answer": "could not get it"})
    agent = build(script, allowed_tools=["memory_recall", "broken"], max_task_steps=9)
    agent.tools.register(Tool(name="broken", description="Always fails.", input_schema={}, handler=explode))
    result = agent.run("use the broken tool")
    assert result.status == "completed"
    assert len(calls) == 2, f"the broken tool ran {len(calls)} times, past the failure limit"
    assert "will not be called again" in provider(agent).prompts[3]


def test_a_working_tool_is_never_capped_by_the_failure_limit() -> None:
    calls: list[dict] = []
    script = [
        {"action": "tool", "reason": "call", "tool": "echo", "arguments": {"n": n}}
        for n in range(5)
    ]
    script.append({"action": "finish", "reason": "ok", "answer": "done"})
    agent = build(script, allowed_tools=["memory_recall", "echo"], max_task_steps=8)
    agent.tools.register(
        Tool(
            name="echo",
            description="Echoes.",
            input_schema={"type": "object", "properties": {"n": {"type": "integer"}}},
            handler=lambda arguments: calls.append(arguments) or f"echo-{arguments['n']}",
        )
    )
    result = agent.run("objective")
    assert result.status == "completed"
    assert len(calls) == 5
