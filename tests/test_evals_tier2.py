"""Tier 2 evals: live small model. Opt in with `pytest -m eval`.

These are a measurement, not a gate. Assertions are on *rates over repetitions*
compared to a recorded baseline, never on a single run — a 4B model that fails
one run in five has not regressed, and a suite that says otherwise gets ignored.
"""

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

from evals import tier2  # noqa: E402
from evals.evaluators import ASSERTIONS  # noqa: E402
from evals.scenarios import LIVE_SCENARIOS  # noqa: E402


pytestmark = pytest.mark.eval


@pytest.fixture(scope="module")
def live_summary():
    ready, reason = tier2.availability()
    if not ready:
        pytest.skip(f"tier 2 needs a live model: {reason}")
    report = tier2.run(repeat=tier2.DEFAULT_REPEAT)
    return tier2.summarise(report)


def test_every_live_scenario_was_measured(live_summary) -> None:
    assert set(live_summary) == {scenario.id for scenario in LIVE_SCENARIOS}


def test_every_run_was_repeated(live_summary) -> None:
    for name, summary in live_summary.items():
        assert summary.runs == tier2.DEFAULT_REPEAT, name


def test_rates_are_reported_for_every_assertion(live_summary) -> None:
    for name, summary in live_summary.items():
        assert set(summary.assertion_rates) == set(ASSERTIONS), name


def test_harness_effort_is_measured(live_summary) -> None:
    for name, summary in live_summary.items():
        assert summary.mean_steps > 0, name
        assert summary.peak_prompt_chars > 0, name


def test_prompts_fit_the_configured_context_window(live_summary) -> None:
    # Four characters per token is a deliberately generous estimate; this is a
    # smoke check that the step prompt has not grown into the window, not a
    # tokeniser.
    budget = tier2.DEFAULT_NUM_CTX * 4
    for name, summary in live_summary.items():
        assert summary.peak_prompt_chars < budget, (
            f"{name} peak prompt {summary.peak_prompt_chars} chars approaches "
            f"the {tier2.DEFAULT_NUM_CTX}-token window"
        )


def test_no_regression_against_the_recorded_baseline(live_summary) -> None:
    baseline = tier2.load_baseline()
    if baseline is None:
        pytest.skip("no baseline recorded; run `python -m evals.tier2 --record`")
    regressions = tier2.compare_to_baseline(live_summary, baseline)
    assert not regressions, "\n".join(regressions)
