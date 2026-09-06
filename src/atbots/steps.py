"""Per-step decision type for the bounded task loop.

Small local models cannot be trusted to honour a JSON Schema that was merely
described to them in a prompt. Declaring the decision as a real output type lets
Pydantic AI constrain and revalidate it with the model server's own structured
output support, which is what makes a 4B model usable in a tool loop.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class TaskStep(BaseModel):
    """One decision: call a permitted tool, or finish with an answer."""

    action: Literal["tool", "finish"]
    reason: str = Field(description="One short sentence explaining the choice.")
    tool: str | None = Field(
        default=None, description="Name of the tool to call when action is 'tool'."
    )
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Arguments for the tool call."
    )
    answer: str | None = Field(
        default=None, description="Final answer when action is 'finish'."
    )

    @model_validator(mode="after")
    def _decision_is_actionable(self) -> "TaskStep":
        """Reject a step the loop cannot act on, in-band.

        Raising here costs a model retry, not a step from the task budget: a 4B
        model routinely answers ``action: "tool"`` without naming one, and being
        told so immediately is far cheaper than spending a step to find out.
        """
        if self.action == "tool" and not self.tool:
            # Not repaired into a finish here even when an answer is present:
            # a model that chose to use a tool and then answered anyway has
            # answered without evidence. Spend a retry making it name the tool.
            raise ValueError(
                "action 'tool' requires 'tool' to be one of the listed tool names; "
                "use action 'finish' with an 'answer' if no tool is needed"
            )
        if self.action == "finish" and not (self.answer or self.reason):
            raise ValueError("action 'finish' requires an 'answer'")
        return self


def step_schema() -> dict[str, Any]:
    """JSON Schema for providers that cannot take a Python output type."""
    schema = TaskStep.model_json_schema()
    schema["title"] = "AtBotTaskStep"
    return schema


STEP_SCHEMA: dict[str, Any] = step_schema()
