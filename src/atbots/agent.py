"""Bounded independent-agent loop driven by installed tools and skills.

The loop is written for small local models. A 4B model does not fail a run; it
fails a step — it invents a tool name, drifts off schema, or repeats itself. So
every failure here becomes an observation the model can read and recover from on
the next step, bounded by the same step budget, rather than an exception that
ends the run.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import uuid
from typing import Any

from atbots.capabilities import Hooks, Tool, ToolRegistry, guard_tool_result, load_skills
from atbots.config import AtBotConfig
from atbots.providers.router import ModelRouter
from atbots.runtime import AtBotRuntime
from atbots.steps import STEP_SCHEMA, TaskStep


SYSTEM_PROMPT = (
    "You are AtBot's bounded task loop. Each turn, choose exactly one permitted "
    "tool call, or finish with a useful answer.\n"
    "Rules:\n"
    "1. Every fact in your answer must come from OBSERVATIONS. You have no other "
    "knowledge of this user, this machine, or this data.\n"
    "2. If the objective needs a fact that is not in OBSERVATIONS, call the tool "
    "that provides it. Do not guess it.\n"
    "3. Never invent a tool result, and never call a tool that is not listed.\n"
    "4. Finish as soon as OBSERVATIONS answer the objective."
)


@dataclass(frozen=True, slots=True)
class Observation:
    """One bounded record of what happened in a step."""

    step: int
    label: str
    status: str
    detail: str

    def render(self) -> str:
        marker = "" if self.status == "ok" else f" [{self.status}]"
        return f"{self.label}{marker}: {self.detail}"


@dataclass(frozen=True, slots=True)
class TaskResult:
    run_id: str
    answer: str
    status: str
    steps: int
    trace: tuple[dict[str, object], ...]


class TaskAgent:
    def __init__(self, config: AtBotConfig, runtime: AtBotRuntime | None = None) -> None:
        self.config = config
        self.runtime = runtime or AtBotRuntime(config)
        self.router = ModelRouter(config)
        self.hooks = Hooks()
        self.tools = ToolRegistry(config.allowed_tools)
        self.tools.register(
            Tool(
                name="memory_recall",
                description="Retrieve governed AtMem memories relevant to a query.",
                input_schema={"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}}},
                handler=self._memory_recall,
            )
        )
        self.skills = load_skills(config.skill_directories)

    def _memory_recall(self, arguments: dict[str, Any]) -> object:
        result = self.runtime.recall(str(arguments.get("query") or ""))
        return [{"memory": row.content, "score": row.score} for row in result.candidates]

    def _observe(self, value: object) -> str:
        return guard_tool_result(value, limit=self.config.observation_char_limit)

    def _prompt(self, objective: str, observations: list[Observation]) -> str:
        """Assemble a step prompt that fits inside a small model's window."""
        window = max(1, self.config.observation_window)
        retained = observations[-window:]
        omitted = len(observations) - len(retained)
        lines = [f"OBJECTIVE: {objective}", "", "TOOLS:"]
        for tool in self.tools.descriptions():
            schema = tool.get("input_schema") or {}
            arguments = ", ".join((schema.get("properties") or {}).keys())
            lines.append(f"- {tool['name']}({arguments}): {tool['description']}")
        if not self.tools.descriptions():
            lines.append("- (none permitted; you must finish)")
        if self.skills:
            lines += ["", "SKILLS: " + ", ".join(skill.name for skill in self.skills)]
        lines += ["", "OBSERVATIONS:"]
        if omitted > 0:
            lines.append(f"- ({omitted} earlier observations omitted)")
        lines += [f"- {item.render()}" for item in retained] or ["- (none yet)"]
        lines += ["", "Choose one permitted tool call, or finish with an answer."]
        return "\n".join(lines)

    def run(self, objective: str, *, remote: bool = False) -> TaskResult:
        if not objective.strip():
            raise ValueError("objective is required")
        run_id = uuid.uuid4().hex
        provider = self.router.select(remote=remote)
        observations: list[Observation] = []
        trace: list[dict[str, object]] = []
        seen: dict[str, tuple[str, str]] = {}
        attempted: set[str] = set()
        tool_failures: dict[str, int] = {}
        nudges = 0
        provider_failures = 0
        self.hooks.emit("task.started", {"run_id": run_id, "tool_count": len(self.tools.descriptions())})
        if "memory_recall" in self.tools.allowed:
            # Memory is a governed input to every independent task, not an
            # optional fact the planning model may guess about or skip.
            try:
                detail = self._observe(self.tools.invoke("memory_recall", {"query": objective}))
                status = "ok"
            except Exception as exc:  # noqa: BLE001 - a preflight failure is not a run failure
                detail, status = f"{type(exc).__name__}: {exc}", "failed"
            observations.append(Observation(0, "memory_recall", status, detail))
            attempted.add("memory_recall")
            trace.append(
                {
                    "step": 0,
                    "action": "tool",
                    "tool": "memory_recall",
                    "status": status,
                    "result_sha256": _digest(detail),
                }
            )
            self.hooks.emit(
                "tool.completed",
                {"run_id": run_id, "step": 0, "tool": "memory_recall", "status": status},
            )
        for step in range(1, self.config.max_task_steps + 1):
            prompt = self._prompt(objective, observations)
            try:
                result = provider.complete(
                    system=SYSTEM_PROMPT,
                    prompt=prompt,
                    schema=STEP_SCHEMA,
                    output_type=TaskStep,
                )
                decision = dict(result.structured or {})
            except Exception as exc:  # noqa: BLE001 - a bad step is recoverable
                provider_failures += 1
                if provider_failures >= self.config.provider_failure_limit:
                    # A model that drifts off schema recovers; a model server
                    # that is misconfigured never does. Report its own words
                    # instead of spending the budget and answering "step limit".
                    reason = f"{type(exc).__name__}: {exc}"
                    trace.append({"step": step, "action": "provider_error", "detail_sha256": _digest(reason)})
                    self.hooks.emit("task.stopped", {"run_id": run_id, "reason": "provider_error"})
                    return TaskResult(
                        run_id,
                        f"The model provider failed on every attempt: {reason}",
                        "provider_error",
                        step,
                        tuple(trace),
                    )
                # Small models drift off schema. Say so and let them try again
                # inside the same step budget rather than ending the run.
                self._recover(
                    observations, trace, step,
                    f"your previous output could not be read ({type(exc).__name__}); "
                    "reply with only the decision fields",
                )
                continue
            provider_failures = 0
            action = decision.get("action")
            if action == "tool" and not decision.get("tool") and decision.get("answer"):
                # Small local models sometimes label an answer derived from a
                # completed preflight tool as another tool action. This repair
                # cannot invoke capability or invent data; it only terminates.
                action = "finish"
            untried = self._untried(attempted)
            if action == "finish" and untried and nudges < self.config.finish_nudges:
                # Small models answer from their priors rather than reaching for
                # a tool they have not tried. One bounded push-back costs a step
                # and usually recovers the call; it is not repeated, so a
                # genuinely toolless objective still finishes.
                nudges += 1
                self._recover(
                    observations, trace, step,
                    "you finished without using " + ", ".join(untried) + ". If the "
                    "objective needs a fact that is not in OBSERVATIONS, call the tool "
                    "that provides it now; if every fact you need is already in "
                    "OBSERVATIONS, finish again.",
                )
                continue
            if action == "finish":
                answer = str(decision.get("answer") or decision.get("reason") or "Task completed.")
                trace.append({"step": step, "action": "finish", "output_sha256": _digest(answer)})
                self.hooks.emit("task.finished", {"run_id": run_id, "steps": step})
                return TaskResult(run_id, answer, "completed", step, tuple(trace))
            if action != "tool" or not decision.get("tool"):
                self._recover(
                    observations, trace, step,
                    "no tool was named; either name one listed tool or finish with an answer",
                )
                continue
            name = str(decision["tool"])
            arguments = decision.get("arguments") or {}
            key = f"{name}:{json.dumps(arguments, default=str, sort_keys=True)}"
            if key in seen:
                # Repetition is the second most common small-model loop failure.
                # Re-running the call would burn the budget recovery depends on.
                # A call that failed counts as repetition too: a model that keeps
                # retrying a broken tool otherwise consumes every step.
                previous, detail = seen[key]
                if previous == "ok":
                    reason = f"{name} was already called with these arguments and returned: {detail}"
                else:
                    reason = (
                        f"{name} was already called with these arguments and {previous}: "
                        f"{detail}. Calling it again will not help — use a different "
                        f"tool or different arguments, or finish and say what you could not get."
                    )
                self._recover(observations, trace, step, reason, label=name)
                continue
            if tool_failures.get(name, 0) >= self.config.tool_failure_limit:
                # Keying repeats on the arguments is not enough: a model that
                # varies them each retry walks straight past that check. A tool
                # that has failed this often is broken, not mis-called.
                self._recover(
                    observations, trace, step,
                    f"{name} has already failed {tool_failures[name]} times and will not be "
                    f"called again. Use a different tool, or finish and say what you could not get.",
                    label=name,
                )
                continue
            try:
                detail = self._observe(self.tools.invoke(name, arguments))
                status = "ok"
            except (PermissionError, ValueError) as exc:
                detail = f"{exc}. Available tools: {self._tool_names() or 'none'}"
                seen[key] = ("was rejected", detail)
                attempted.add(name)
                self._recover(observations, trace, step, detail, label=name, status="rejected")
                continue
            except Exception as exc:  # noqa: BLE001 - a tool fault is an observation
                detail = f"{type(exc).__name__}: {exc}"
                seen[key] = ("failed", detail)
                attempted.add(name)
                tool_failures[name] = tool_failures.get(name, 0) + 1
                self._recover(observations, trace, step, detail, label=name, status="failed")
                continue
            seen[key] = (status, detail)
            attempted.add(name)
            observations.append(Observation(step, name, status, detail))
            trace.append(
                {"step": step, "action": "tool", "tool": name, "status": status, "result_sha256": _digest(detail)}
            )
            self.hooks.emit("tool.completed", {"run_id": run_id, "step": step, "tool": name, "status": status})
        self.hooks.emit("task.stopped", {"run_id": run_id, "reason": "step_limit"})
        return TaskResult(
            run_id,
            _step_limit_answer(observations),
            "step_limit",
            self.config.max_task_steps,
            tuple(trace),
        )

    def _tool_names(self) -> str:
        return ", ".join(tool["name"] for tool in self.tools.descriptions())

    def _untried(self, attempted: set[str]) -> list[str]:
        """Permitted tools the model has not called at all yet.

        A tool that was called and failed counts as attempted: pushing the model
        back towards a tool that already raised wastes the step it costs.
        """
        return [
            tool["name"]
            for tool in self.tools.descriptions()
            if tool["name"] not in attempted
        ]

    def _recover(
        self,
        observations: list[Observation],
        trace: list[dict[str, object]],
        step: int,
        detail: str,
        *,
        label: str = "model",
        status: str = "rejected",
    ) -> None:
        bounded = detail[: self.config.observation_char_limit]
        observations.append(Observation(step, label, status, bounded))
        trace.append({"step": step, "action": "recover", "tool": label, "status": status, "detail_sha256": _digest(bounded)})
        self.hooks.emit("step.recovered", {"step": step, "tool": label, "status": status})


def _step_limit_answer(observations: list[Observation]) -> str:
    useful = [item for item in observations if item.status == "ok"]
    if not useful:
        return "Task stopped at the configured step limit before any tool succeeded."
    return (
        "Task stopped at the configured step limit. Last successful observation — "
        + useful[-1].render()
    )


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()
