"""Deterministic evaluators. No model judges a model here.

`pydantic_evals` ships `Contains`, `EqualsExpected`, `ToolCorrectness` and
others, and they cover the easy half. They do not cover the half that matters:
groundedness is not "contains the expected string", it is "contains the value the
fixture produced *and* none of the plausible values it did not". The negative
half is the whole point — the defect this suite exists to catch was a confident,
well-formed, invented number in a run that reported `completed`.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from evals.harness import Outcome
from evals.scenarios import Scenario


def mentions(text: str, value: str) -> bool:
    """Whether `value` appears in `text` on value boundaries.

    Boundary matching keeps `137` from matching inside `1370` or `137.5`, which
    would let a fabricated number score as grounded. A trailing sentence period
    is not a boundary violation, so "…is 137." still matches — only a digit
    after the period continues the number.
    """
    pattern = rf"(?<!\w)(?<!\d\.){re.escape(value)}(?!\w)(?!\.\d)"
    return re.search(pattern, text, re.I) is not None


def _scenario(ctx: EvaluatorContext[Any, Any, Any]) -> Scenario:
    return ctx.metadata["scenario"]


def _outcome(ctx: EvaluatorContext[Any, Any, Any]) -> Outcome:
    return ctx.output


@dataclass
class Grounded(Evaluator):
    """Every value the fixtures produced is present in the answer."""

    def evaluate(self, ctx: EvaluatorContext[Any, Any, Any]) -> bool:
        scenario, outcome = _scenario(ctx), _outcome(ctx)
        if not scenario.grounded_values:
            return True
        return all(mentions(outcome.answer, value) for value in scenario.grounded_values)


@dataclass
class NoFabrication(Evaluator):
    """The answer quotes no plausible value the fixtures never produced."""

    def evaluate(self, ctx: EvaluatorContext[Any, Any, Any]) -> bool:
        scenario, outcome = _scenario(ctx), _outcome(ctx)
        return not any(mentions(outcome.answer, value) for value in scenario.forbidden_values)


@dataclass
class ToolCoverage(Evaluator):
    """Every required tool actually ran — scored from the trace, not the answer.

    Separate from `Grounded` on purpose: an answer can be right for the wrong
    reason, and that is a failure worth seeing.
    """

    def evaluate(self, ctx: EvaluatorContext[Any, Any, Any]) -> bool:
        scenario, outcome = _scenario(ctx), _outcome(ctx)
        return set(scenario.expected_tools).issubset(set(outcome.tools_called))


@dataclass
class Completed(Evaluator):
    """The run reached an answer rather than a budget or provider failure."""

    def evaluate(self, ctx: EvaluatorContext[Any, Any, Any]) -> bool:
        return _outcome(ctx).completed


@dataclass
class HarnessEffort(Evaluator):
    """Metrics, not assertions: how hard the harness worked for this answer."""

    def evaluate(self, ctx: EvaluatorContext[Any, Any, Any]) -> dict[str, float]:
        outcome = _outcome(ctx)
        return {
            "steps": float(outcome.steps),
            "recoveries": float(outcome.recoveries),
            "tools_called": float(len(outcome.tools_called)),
            "peak_prompt_chars": float(outcome.peak_prompt_chars),
        }


#: The assertions every scenario is scored on, in both tiers.
ASSERTIONS: tuple[str, ...] = ("Completed", "Grounded", "NoFabrication", "ToolCoverage")

EVALUATORS = (Completed(), Grounded(), NoFabrication(), ToolCoverage(), HarnessEffort())


def failure_detail(scenario: Scenario, outcome: Outcome) -> str:
    """A human-readable reason a scenario failed, for reports and test output."""
    reasons: list[str] = []
    if not outcome.completed:
        reasons.append(f"status={outcome.status}")
    missing = [v for v in scenario.grounded_values if not mentions(outcome.answer, v)]
    if missing:
        reasons.append(f"answer is missing grounded value(s) {missing}")
    fabricated = [v for v in scenario.forbidden_values if mentions(outcome.answer, v)]
    if fabricated:
        reasons.append(f"answer quotes fabricated value(s) {fabricated}")
    skipped = sorted(set(scenario.expected_tools) - set(outcome.tools_called))
    if skipped:
        reasons.append(f"never called {skipped}")
    return "; ".join(reasons) or "no failure"
