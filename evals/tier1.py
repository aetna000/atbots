"""Tier 1: the harness gate. Scripted model, no network, runs on every commit."""

from __future__ import annotations

from typing import Any

from pydantic_evals import Case, Dataset

from evals.evaluators import EVALUATORS
from evals.harness import Outcome, run_scripted
from evals.scenarios import SCENARIOS, SCENARIOS_BY_ID, Scenario


def task(scenario_id: str) -> Outcome:
    return run_scripted(SCENARIOS_BY_ID[scenario_id])


def build_dataset(scenarios: tuple[Scenario, ...] = SCENARIOS) -> Dataset:
    return Dataset(
        name="atbots-harness-tier1",
        cases=[
            Case(
                name=scenario.id,
                inputs=scenario.id,
                metadata={"scenario": scenario, "negative_control": scenario.negative_control},
            )
            for scenario in scenarios
        ],
        evaluators=EVALUATORS,
    )


def run(progress: bool = False) -> Any:
    return build_dataset().evaluate_sync(task, progress=progress)


if __name__ == "__main__":
    run(progress=True).print(include_input=False, include_output=False)
