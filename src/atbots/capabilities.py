"""Typed tool, skill, hook, guardrail, and policy primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Callable


ToolHandler = Callable[[dict[str, Any]], object]
HookHandler = Callable[[str, dict[str, Any]], None]


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler
    destructive: bool = False


class ToolRegistry:
    def __init__(self, allowed: list[str]) -> None:
        self.allowed = frozenset(allowed)
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def descriptions(self) -> list[dict[str, object]]:
        return [
            {"name": tool.name, "description": tool.description, "input_schema": tool.input_schema}
            for name, tool in sorted(self._tools.items())
            if name in self.allowed
        ]

    def invoke(self, name: str, arguments: dict[str, Any]) -> object:
        if name not in self.allowed:
            raise PermissionError(f"tool is not permitted by this capability profile: {name}")
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"tool is not installed: {name}")
        if tool.destructive:
            raise PermissionError(f"destructive tool requires a separate approval boundary: {name}")
        return tool.handler(arguments)


@dataclass(frozen=True, slots=True)
class Skill:
    name: str
    instructions: str
    source: str


def load_skills(directories: list[str]) -> tuple[Skill, ...]:
    skills: list[Skill] = []
    for directory in directories:
        root = Path(directory).expanduser().resolve(strict=False)
        if not root.is_dir():
            continue
        for source in sorted(root.glob("*/SKILL.md")):
            text = source.read_text(encoding="utf-8")
            if len(text) <= 100_000:
                skills.append(Skill(source.parent.name, text, str(source)))
    return tuple(skills)


class Hooks:
    def __init__(self) -> None:
        self._handlers: list[HookHandler] = []

    def add(self, handler: HookHandler) -> None:
        self._handlers.append(handler)

    def emit(self, event: str, payload: dict[str, Any]) -> None:
        # Callers must provide content-free metadata suitable for traces.
        json.dumps(payload)
        for handler in tuple(self._handlers):
            handler(event, payload)


def guard_tool_result(value: object, *, limit: int = 20_000) -> str:
    text = json.dumps(value, default=str, sort_keys=True)
    if len(text) > limit:
        return text[:limit] + "…[truncated]"
    return text
