"""Run one scenario and record what the loop actually did."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from atbots.agent import TaskAgent
from atbots.config import AtBotConfig, ProviderConfig
from atbots.domain import ProviderResult
from atbots.steps import TaskStep

from evals.fixtures import TOOLS, StubMemory
from evals.scenarios import Scenario


@dataclass(frozen=True)
class Outcome:
    """Everything the evaluators score, from one run."""

    answer: str
    status: str
    steps: int
    tools_called: tuple[str, ...]
    recoveries: int
    peak_prompt_chars: int
    trace: tuple[dict[str, object], ...] = ()

    @property
    def completed(self) -> bool:
        return self.status == "completed"


class ScriptedProvider:
    """Replays a fixed list of model behaviours. Tier 1 only."""

    name = "scripted"
    model = "scripted-model"
    egress_class = "local"

    #: Answer used when a script runs out. A scenario that reaches this has a
    #: mis-specified script, so it is made loud rather than silently plausible.
    EXHAUSTED = "SCRIPT EXHAUSTED"

    def __init__(self, script: tuple[Any, ...]) -> None:
        self.script = list(script)
        self.prompts: list[str] = []
        self.exhausted = False

    def available(self) -> bool:
        return True

    def complete(self, *, system, prompt, schema=None, output_type=None) -> ProviderResult:
        del system, schema, output_type
        self.prompts.append(prompt)
        if self.script:
            step = self.script.pop(0)
        else:
            self.exhausted = True
            step = {"action": "finish", "reason": self.EXHAUSTED, "answer": self.EXHAUSTED}
        if isinstance(step, Exception):
            raise step
        return ProviderResult(
            text=json.dumps(step), structured=step, provider=self.name,
            model=self.model, egress_class=self.egress_class,
        )


class RecordingProvider:
    """Wraps a real provider and records the size of each step prompt.

    Peak prompt size is not visible from the task result, and measuring it inside
    `agent.py` would put eval concerns into shipped code.
    """

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.prompts: list[str] = []

    @property
    def name(self) -> str:
        return self.inner.name

    @property
    def model(self) -> str:
        return self.inner.model

    @property
    def egress_class(self) -> str:
        return self.inner.egress_class

    def available(self) -> bool:
        return self.inner.available()

    def complete(self, *, system, prompt, schema=None, output_type=None) -> ProviderResult:
        self.prompts.append(prompt)
        return self.inner.complete(system=system, prompt=prompt, schema=schema, output_type=output_type)


def build_agent(scenario: Scenario, config: AtBotConfig) -> TaskAgent:
    agent = TaskAgent(config, runtime=StubMemory())
    for name in scenario.tools:
        agent.tools.register(TOOLS[name])
    return agent


def eval_config(scenario: Scenario, provider: ProviderConfig | None = None) -> AtBotConfig:
    return AtBotConfig(
        allowed_tools=["memory_recall", *scenario.tools],
        max_task_steps=scenario.max_steps,
        providers=[provider] if provider else [ProviderConfig()],
    )


def run_scenario(scenario: Scenario, *, provider: Any, config: AtBotConfig) -> Outcome:
    """Run one scenario against one provider and summarise the run."""
    agent = build_agent(scenario, config)
    recorder = RecordingProvider(provider)
    agent.router._providers = [recorder]  # noqa: SLF001 - the eval seam
    result = agent.run(scenario.objective)
    tools_called = tuple(
        str(row["tool"])
        for row in result.trace
        if row.get("action") == "tool" and row.get("status") == "ok"
    )
    recoveries = sum(1 for row in result.trace if row.get("action") == "recover")
    return Outcome(
        answer=result.answer,
        status=result.status,
        steps=result.steps,
        tools_called=tools_called,
        recoveries=recoveries,
        peak_prompt_chars=max((len(text) for text in recorder.prompts), default=0),
        trace=result.trace,
    )


def run_scripted(scenario: Scenario) -> Outcome:
    """Tier 1: the model is a script, so the harness is the only variable."""
    provider = ScriptedProvider(scenario.script)
    outcome = run_scenario(scenario, provider=provider, config=eval_config(scenario))
    if provider.exhausted:
        # The script did not anticipate every step the harness takes — a nudge
        # or a recovery. Fail loudly instead of scoring a meaningless run.
        raise AssertionError(
            f"scenario {scenario.id!r} ran out of scripted steps after "
            f"{outcome.steps} steps; the script must cover every step the loop takes"
        )
    return outcome
