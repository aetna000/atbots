"""Bounded independent-agent loop driven by installed tools and skills."""

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


STEP_SCHEMA: dict[str, Any] = {
    "title": "AtBotTaskStep",
    "type": "object",
    "required": ["action", "reason"],
    "properties": {
        "action": {"enum": ["tool", "finish"]},
        "reason": {"type": "string"},
        "tool": {"type": ["string", "null"]},
        "arguments": {"type": "object"},
        "answer": {"type": ["string", "null"]},
    },
}


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

    def run(self, objective: str, *, remote: bool = False) -> TaskResult:
        if not objective.strip():
            raise ValueError("objective is required")
        run_id = uuid.uuid4().hex
        provider = self.router.select(remote=remote)
        observations: list[str] = []
        trace: list[dict[str, object]] = []
        skill_names = [skill.name for skill in self.skills]
        self.hooks.emit("task.started", {"run_id": run_id, "tool_count": len(self.tools.descriptions())})
        if "memory_recall" in self.tools.allowed:
            # Memory is a governed input to every independent task, not an
            # optional fact the planning model may guess about or skip.
            value = self.tools.invoke("memory_recall", {"query": objective})
            observation = guard_tool_result(value)
            observations.append(f"memory_recall: {observation}")
            trace.append(
                {
                    "step": 0,
                    "action": "tool",
                    "tool": "memory_recall",
                    "result_sha256": _digest(observation),
                }
            )
            self.hooks.emit(
                "tool.completed",
                {"run_id": run_id, "step": 0, "tool": "memory_recall"},
            )
        for step in range(1, self.config.max_task_steps + 1):
            prompt = json.dumps(
                {
                    "objective": objective,
                    "tools": self.tools.descriptions(),
                    "skills": skill_names,
                    "observations": observations,
                    "instruction": "Choose one permitted tool call or finish with a useful answer.",
                },
                sort_keys=True,
            )
            result = provider.complete(
                system="You are AtBot's bounded task loop. Never invent tool results. Return only the requested JSON.",
                prompt=prompt,
                schema=STEP_SCHEMA,
            )
            decision = result.structured or {}
            action = decision.get("action")
            if action == "tool" and not decision.get("tool") and decision.get("answer"):
                # Small local models sometimes label an answer derived from a
                # completed preflight tool as another tool action. This repair
                # cannot invoke capability or invent data; it only terminates.
                action = "finish"
            if action == "finish":
                answer = str(decision.get("answer") or decision.get("reason") or "Task completed.")
                trace.append({"step": step, "action": "finish", "output_sha256": _digest(answer)})
                self.hooks.emit("task.finished", {"run_id": run_id, "steps": step})
                return TaskResult(run_id, answer, "completed", step, tuple(trace))
            if action != "tool" or not decision.get("tool"):
                raise RuntimeError("model returned an invalid task action")
            name = str(decision["tool"])
            value = self.tools.invoke(name, decision.get("arguments") or {})
            observation = guard_tool_result(value)
            observations.append(f"{name}: {observation}")
            trace.append({"step": step, "action": "tool", "tool": name, "result_sha256": _digest(observation)})
            self.hooks.emit("tool.completed", {"run_id": run_id, "step": step, "tool": name})
        self.hooks.emit("task.stopped", {"run_id": run_id, "reason": "step_limit"})
        return TaskResult(run_id, "Task stopped at the configured step limit.", "step_limit", self.config.max_task_steps, tuple(trace))


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()
