"""Tier 1 evals: the harness gate. Scripted model, no network, every commit."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

pytest.importorskip(
    "pydantic_evals",
    reason='evals need the eval extra: pip install -e ".[evals]"',
)

from evals.evaluators import ASSERTIONS, failure_detail  # noqa: E402
from evals.harness import run_scripted  # noqa: E402
from evals.scenarios import LIVE_SCENARIOS, SCENARIOS, SCENARIOS_BY_ID  # noqa: E402
from evals.tier1 import run  # noqa: E402


@pytest.fixture(scope="module")
def report():
    return run()


@pytest.fixture(scope="module")
def cases(report):
    return {case.name: case for case in report.cases}


def test_every_scenario_produced_a_case(cases) -> None:
    assert set(cases) == {scenario.id for scenario in SCENARIOS}


def test_no_evaluator_errored(report) -> None:
    assert report.failures == []


@pytest.mark.parametrize("scenario", LIVE_SCENARIOS, ids=lambda s: s.id)
def test_scenario_passes_every_assertion(scenario, cases) -> None:
    case = cases[scenario.id]
    failed = [name for name, result in case.assertions.items() if not result.value]
    assert not failed, (
        f"{scenario.id} failed {failed}: "
        f"{failure_detail(scenario, run_scripted(scenario))}"
    )


def test_the_negative_control_is_caught(cases) -> None:
    """Proof the evaluators have teeth.

    This scenario's model answers "about 10 gigabytes" without calling the tool.
    The run completes and raises nothing — the exact shape of the defect that
    motivated these evals. Everything except `Completed` must fail.
    """
    case = cases["fabricated_answer_is_caught"]
    assert case.assertions["Completed"].value is True
    for name in ("Grounded", "NoFabrication", "ToolCoverage"):
        assert case.assertions[name].value is False, f"{name} did not catch the fabrication"


def test_the_negative_control_names_the_fabricated_value() -> None:
    scenario = SCENARIOS_BY_ID["fabricated_answer_is_caught"]
    detail = failure_detail(scenario, run_scripted(scenario))
    assert "fabricated value(s) ['10']" in detail
    assert "never called ['disk_free']" in detail


def test_every_scenario_is_scored_on_the_same_assertions(cases) -> None:
    for name, case in cases.items():
        assert set(case.assertions) == set(ASSERTIONS), f"{name} was scored differently"


def test_harness_effort_is_recorded(cases) -> None:
    for name, case in cases.items():
        scores = {key: result.value for key, result in case.scores.items()}
        assert set(scores) >= {"steps", "recoveries", "tools_called", "peak_prompt_chars"}, name
        assert scores["peak_prompt_chars"] > 0, name


def test_recoveries_are_counted(cases) -> None:
    # This scenario's model emits a provider failure and an off-schema decision
    # before answering; both must show up as harness effort.
    assert cases["recovers_from_malformed_steps"].scores["recoveries"].value == 2


def test_oversized_tool_result_stays_inside_the_budget(cases) -> None:
    # The fixture returns 40,000 characters; the step prompt must not carry them.
    assert cases["survives_oversized_result"].scores["peak_prompt_chars"].value < 4_000


def test_tier1_never_touches_the_network(monkeypatch) -> None:
    import socket

    def forbidden(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("Tier 1 must not open a socket")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    for scenario in SCENARIOS:
        run_scripted(scenario)
