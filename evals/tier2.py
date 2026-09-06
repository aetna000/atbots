"""Tier 2: measurement against a real local model.

Statistical, not binary. Each scenario runs N times and is reported as a rate,
because a single run of a 4B model tells you nothing you can act on. Never part
of the default gate — a measurement used as a gate becomes noise people learn to
ignore.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import statistics
from typing import Any

from pydantic_evals import Case, Dataset

from atbots.config import AtBotConfig, ProviderConfig
from atbots.providers.pydantic_ai import PydanticAIProvider

from evals.evaluators import ASSERTIONS, EVALUATORS
from evals.harness import Outcome, eval_config, run_scenario
from evals.scenarios import LIVE_SCENARIOS, SCENARIOS_BY_ID, Scenario


BASELINE_PATH = Path(__file__).resolve().parent / "baseline.json"

DEFAULT_MODEL = os.environ.get("ATBOTS_EVAL_MODEL", "qwen3:4b")
DEFAULT_ENDPOINT = os.environ.get("ATBOTS_EVAL_ENDPOINT", "http://127.0.0.1:11434")
DEFAULT_NUM_CTX = int(os.environ.get("ATBOTS_EVAL_NUM_CTX", "8192"))
DEFAULT_REPEAT = int(os.environ.get("ATBOTS_EVAL_REPEAT", "3"))

#: How far below baseline a rate may drift before it is called a regression.
#: Wide on purpose: with a handful of repetitions, ordinary variance is large.
DEFAULT_TOLERANCE = 0.2


def provider_config(model: str = DEFAULT_MODEL) -> ProviderConfig:
    return ProviderConfig(model=model, endpoint=DEFAULT_ENDPOINT, num_ctx=DEFAULT_NUM_CTX)


def build_provider(model: str = DEFAULT_MODEL) -> PydanticAIProvider:
    row = provider_config(model)
    return PydanticAIProvider(
        name=row.name, model=row.model, endpoint=row.endpoint,
        kind=row.kind, num_ctx=row.num_ctx, egress_class=row.egress_class,
    )


def availability(model: str = DEFAULT_MODEL) -> tuple[bool, str]:
    """Whether Tier 2 can run, and why not when it cannot."""
    try:
        provider = build_provider(model)
    except ValueError as exc:
        return False, str(exc)
    if provider.available():
        return True, ""
    return False, provider.unavailable_reason or "the model provider is unavailable"


def task(scenario_id: str) -> Outcome:
    scenario = SCENARIOS_BY_ID[scenario_id]
    config: AtBotConfig = eval_config(scenario, provider_config())
    return run_scenario(scenario, provider=build_provider(), config=config)


def build_dataset(scenarios: tuple[Scenario, ...] = LIVE_SCENARIOS) -> Dataset:
    return Dataset(
        name="atbots-small-model-tier2",
        cases=[
            Case(name=s.id, inputs=s.id, metadata={"scenario": s, "negative_control": False})
            for s in scenarios
        ],
        evaluators=EVALUATORS,
    )


@dataclass(frozen=True)
class ScenarioSummary:
    """Rates and means for one scenario over N repetitions."""

    runs: int
    success_rate: float
    assertion_rates: dict[str, float]
    mean_steps: float
    mean_recoveries: float
    peak_prompt_chars: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "runs": self.runs,
            "success_rate": round(self.success_rate, 3),
            "assertion_rates": {k: round(v, 3) for k, v in self.assertion_rates.items()},
            "mean_steps": round(self.mean_steps, 2),
            "mean_recoveries": round(self.mean_recoveries, 2),
            "peak_prompt_chars": round(self.peak_prompt_chars),
        }


def summarise(report: Any) -> dict[str, ScenarioSummary]:
    """Aggregate repeated cases back into one summary per scenario."""
    grouped: dict[str, list[Any]] = {}
    for case in report.cases:
        key = case.source_case_name or case.name
        grouped.setdefault(key, []).append(case)
    summary: dict[str, ScenarioSummary] = {}
    for name, cases in grouped.items():
        rates = {
            assertion: _rate(cases, assertion) for assertion in ASSERTIONS
        }
        passed = sum(
            1 for case in cases
            if all(result.value for result in case.assertions.values())
        )
        summary[name] = ScenarioSummary(
            runs=len(cases),
            success_rate=passed / len(cases),
            assertion_rates=rates,
            mean_steps=statistics.fmean(_score(cases, "steps")),
            mean_recoveries=statistics.fmean(_score(cases, "recoveries")),
            peak_prompt_chars=max(_score(cases, "peak_prompt_chars")),
        )
    return summary


def _rate(cases: list[Any], assertion: str) -> float:
    values = [case.assertions[assertion].value for case in cases if assertion in case.assertions]
    return (sum(1 for value in values if value) / len(values)) if values else 0.0


def _score(cases: list[Any], key: str) -> list[float]:
    return [case.scores[key].value for case in cases if key in case.scores] or [0.0]


def load_baseline(path: Path = BASELINE_PATH) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def compare_to_baseline(
    summary: dict[str, ScenarioSummary],
    baseline: dict[str, Any],
    tolerance: float = DEFAULT_TOLERANCE,
) -> list[str]:
    """Scenarios whose rates dropped further than tolerance allows."""
    regressions: list[str] = []
    recorded = baseline.get("scenarios", {})
    for name, expected in recorded.items():
        observed = summary.get(name)
        if observed is None:
            regressions.append(f"{name}: missing from this run")
            continue
        floor = expected["success_rate"] - tolerance
        if observed.success_rate < floor:
            regressions.append(
                f"{name}: success {observed.success_rate:.2f} < baseline "
                f"{expected['success_rate']:.2f} - {tolerance:.2f}"
            )
        for assertion, expected_rate in expected.get("assertion_rates", {}).items():
            got = observed.assertion_rates.get(assertion, 0.0)
            if got < expected_rate - tolerance:
                regressions.append(
                    f"{name}.{assertion}: {got:.2f} < baseline {expected_rate:.2f} - {tolerance:.2f}"
                )
    return regressions


def run(repeat: int = DEFAULT_REPEAT, progress: bool = False) -> Any:
    # Concurrency is left at the default: a laptop serving one small model gains
    # nothing from parallel requests and the timings stop meaning anything.
    return build_dataset().evaluate_sync(task, repeat=repeat, progress=progress)


def as_baseline(summary: dict[str, ScenarioSummary], model: str, repeat: int) -> dict[str, Any]:
    return {
        "model": model,
        "repeat": repeat,
        "tolerance": DEFAULT_TOLERANCE,
        "scenarios": {name: value.to_dict() for name, value in sorted(summary.items())},
    }


def main() -> int:
    ready, reason = availability()
    if not ready:
        print(f"tier 2 skipped: {reason}")
        return 0
    report = run(progress=True)
    report.print(include_input=False, include_output=False)
    summary = summarise(report)
    print()
    print(f"model={DEFAULT_MODEL} num_ctx={DEFAULT_NUM_CTX} repeat={DEFAULT_REPEAT}")
    for name, value in sorted(summary.items()):
        rates = " ".join(f"{k}={v:.2f}" for k, v in value.assertion_rates.items())
        print(
            f"  {name:32} success={value.success_rate:.2f}  {rates}  "
            f"steps={value.mean_steps:.1f} recoveries={value.mean_recoveries:.1f}"
        )
    baseline = load_baseline()
    if baseline is None:
        print("\nno baseline recorded; write one with --record")
        return 0
    regressions = compare_to_baseline(summary, baseline)
    print()
    if regressions:
        print("REGRESSIONS vs baseline:")
        for line in regressions:
            print(f"  - {line}")
        return 1
    print(f"no regressions vs baseline ({baseline['model']}, repeat={baseline['repeat']})")
    return 0


if __name__ == "__main__":
    import sys

    if "--record" in sys.argv:
        ready, reason = availability()
        if not ready:
            print(f"cannot record: {reason}")
            raise SystemExit(1)
        report = run(progress=True)
        payload = as_baseline(summarise(report), DEFAULT_MODEL, DEFAULT_REPEAT)
        BASELINE_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"baseline written: {BASELINE_PATH}")
        raise SystemExit(0)
    raise SystemExit(main())
