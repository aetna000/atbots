"""Deterministic tools and memory, so the model is the only variable."""

from __future__ import annotations

from typing import Any

from atbots.capabilities import Tool


# Values a grounded answer must be able to quote. They are deliberately
# arbitrary: a model cannot arrive at 137 or 482 from its priors.
DISK_FREE_GB = 137
LINE_COUNT = 482
TEMPERATURE_C = 9

MEMORY_FACT = "The user's laptop is a Mac with 16GB of RAM."


def _disk_free(arguments: dict[str, Any]) -> object:
    return {"path": str(arguments.get("path") or "/"), "free_gb": DISK_FREE_GB}


def _count_lines(arguments: dict[str, Any]) -> object:
    return {"path": str(arguments.get("path") or "README.md"), "lines": LINE_COUNT}


def _weather(arguments: dict[str, Any]) -> object:
    return {"city": str(arguments.get("city") or "Sydney"), "celsius": TEMPERATURE_C}


def _huge(arguments: dict[str, Any]) -> object:
    del arguments
    return {"note": "x" * 40_000, "free_gb": DISK_FREE_GB}


def _broken(arguments: dict[str, Any]) -> object:
    del arguments
    raise RuntimeError("the fixture tool failed on purpose")


TOOLS: dict[str, Tool] = {
    "disk_free": Tool(
        name="disk_free",
        description="Free disk space in gigabytes for a path.",
        input_schema={"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}}},
        handler=_disk_free,
    ),
    "count_lines": Tool(
        name="count_lines",
        description="Number of lines in a file.",
        input_schema={"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}}},
        handler=_count_lines,
    ),
    "weather": Tool(
        name="weather",
        description="Current temperature in celsius for a city.",
        input_schema={"type": "object", "required": ["city"], "properties": {"city": {"type": "string"}}},
        handler=_weather,
    ),
    "huge_report": Tool(
        name="huge_report",
        description="A report far larger than the observation budget.",
        input_schema={"type": "object", "properties": {}},
        handler=_huge,
    ),
    "broken_tool": Tool(
        name="broken_tool",
        description="A tool whose handler always raises.",
        input_schema={"type": "object", "properties": {}},
        handler=_broken,
    ),
}


class StubMemory:
    """A memory runtime with one fixed fact and no vendor behind it."""

    def recall(self, query: str) -> object:
        del query
        row = type("Row", (), {"content": MEMORY_FACT, "score": 1.0})()
        return type("Result", (), {"candidates": [row]})()
