"""The scenario list. Adding an eval case means editing SCENARIOS and nothing else."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from evals.fixtures import DISK_FREE_GB, LINE_COUNT, TEMPERATURE_C


@dataclass(frozen=True)
class Scenario:
    """One task, plus what a correct and honest answer looks like."""

    id: str
    objective: str
    tools: tuple[str, ...]
    expected_tools: tuple[str, ...] = ()
    grounded_values: tuple[str, ...] = ()
    forbidden_values: tuple[str, ...] = ()
    max_steps: int = 6
    # Tier 1 only: the model behaviours to replay, in order. An Exception is
    # raised as a provider failure; a dict is returned as a decision.
    script: tuple[Any, ...] = ()
    # A negative control is expected to fail its evaluators; the suite asserts
    # that it does, which is what proves the evaluators have teeth.
    negative_control: bool = False


def _finish(answer: str, reason: str = "done") -> dict[str, Any]:
    return {"action": "finish", "reason": reason, "answer": answer}


def _call(tool: str, **arguments: Any) -> dict[str, Any]:
    return {"action": "tool", "reason": f"calling {tool}", "tool": tool, "arguments": arguments}


DISK = str(DISK_FREE_GB)
LINES = str(LINE_COUNT)
TEMP = str(TEMPERATURE_C)


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        id="single_tool",
        objective="How much free disk space is on / ? Answer with the number.",
        tools=("disk_free",),
        expected_tools=("disk_free",),
        grounded_values=(DISK,),
        # Round numbers a model reaches for when it guesses instead of calling.
        forbidden_values=("10", "50", "100", "256", "512"),
        script=(_call("disk_free", path="/"), _finish(f"There are {DISK} GB free on /.")),
    ),
    Scenario(
        id="two_tools",
        objective=(
            "How much free disk space is on / , and how many lines are in README.md? "
            "Answer with both numbers."
        ),
        tools=("disk_free", "count_lines"),
        expected_tools=("disk_free", "count_lines"),
        grounded_values=(DISK, LINES),
        forbidden_values=("10", "100", "1000"),
        script=(
            _call("disk_free", path="/"),
            _call("count_lines", path="README.md"),
            _finish(f"{DISK} GB free, and README.md has {LINES} lines."),
        ),
    ),
    Scenario(
        id="recovers_from_malformed_steps",
        objective="What is the temperature in Sydney? Answer with the number.",
        tools=("weather",),
        expected_tools=("weather",),
        grounded_values=(TEMP,),
        forbidden_values=("22", "25", "30"),
        script=(
            RuntimeError("the model returned prose, not a decision"),
            {"action": "wander", "reason": "off schema"},
            _call("weather", city="Sydney"),
            _finish(f"It is {TEMP} degrees celsius in Sydney."),
        ),
    ),
    Scenario(
        id="recovers_from_invented_tool",
        objective="How much free disk space is on / ? Answer with the number.",
        tools=("disk_free",),
        expected_tools=("disk_free",),
        grounded_values=(DISK,),
        forbidden_values=("10", "100"),
        script=(
            _call("web_search", query="disk space"),
            _call("disk_free", path="/"),
            _finish(f"{DISK} GB are free."),
        ),
    ),
    Scenario(
        id="recovers_from_repeat",
        objective="How many lines are in README.md? Answer with the number.",
        tools=("count_lines",),
        expected_tools=("count_lines",),
        grounded_values=(LINES,),
        forbidden_values=("100", "500"),
        script=(
            _call("count_lines", path="README.md"),
            _call("count_lines", path="README.md"),
            _finish(f"README.md has {LINES} lines."),
        ),
    ),
    Scenario(
        id="survives_oversized_result",
        objective="Read the huge report and state the free_gb value it contains.",
        tools=("huge_report",),
        expected_tools=("huge_report",),
        grounded_values=(DISK,),
        forbidden_values=("10", "100"),
        script=(_call("huge_report"), _finish(f"The report gives free_gb as {DISK}.")),
    ),
    Scenario(
        id="survives_failing_tool",
        objective="Try the broken tool, then say plainly that you could not get the value.",
        tools=("broken_tool",),
        grounded_values=("could not",),
        forbidden_values=(DISK, "137"),
        # The loop pushes back on a finish that never used an available tool,
        # so an honest model answers twice: once, then again after the nudge.
        script=(
            _call("broken_tool"),
            _finish("The tool failed, so I could not get the value."),
            _finish("The tool failed, so I could not get the value."),
        ),
    ),
    Scenario(
        id="fabricated_answer_is_caught",
        objective="How much free disk space is on / ? Answer with the number.",
        tools=("disk_free",),
        expected_tools=("disk_free",),
        grounded_values=(DISK,),
        forbidden_values=("10",),
        # The exact defect that motivated this feature: a confident, well-formed,
        # invented number, from a run that reports `completed`.
        script=(
            _finish("There are about 10 gigabytes free on /."),
            _finish("There are about 10 gigabytes free on /."),
        ),
        negative_control=True,
    ),
)


SCENARIOS_BY_ID: dict[str, Scenario] = {scenario.id: scenario for scenario in SCENARIOS}

# Tier 2 asks a real model; the scripts and the negative control are Tier 1 only.
LIVE_SCENARIOS: tuple[Scenario, ...] = tuple(
    scenario for scenario in SCENARIOS if not scenario.negative_control
)
