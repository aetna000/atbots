import json
from pathlib import Path

import pytest
from pydantic_ai.models.test import TestModel

from atbots.platform.control import ControlPlan, ControlRoom
from atbots.platform.store import AgentStore

CASES = json.loads(
    (Path(__file__).resolve().parents[1] / "evals/platform-intents-v1.json").read_text()
)["cases"]


def test_creation_fixture_does_not_precreate_its_target():
    for case in CASES:
        if case["expected"]["action"] == "create":
            assert case["expected"]["name"] not in case["initial_agents"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["text"][:50])
def test_native_typed_intent_and_no_unapproved_mutation(case, tmp_path):
    store = AgentStore(tmp_path)
    model = TestModel(custom_output_text=json.dumps(case["expected"]))
    room = ControlRoom(store, model=model)
    plan = room.plan(case["text"])
    assert plan == ControlPlan.model_validate(case["expected"])
    assert [a.name for a in store.list()] == ["control-room"]
    assert store.receipts("control-room")[-1]["status"] == "replied"


def test_readonly_plan_rejects_irrelevant_schedule_or_delegation_fields():
    with pytest.raises(ValueError):
        ControlPlan(action="list", cron="* * * * *")
    with pytest.raises(ValueError):
        ControlPlan(action="list", delegation_id="a" * 32)


def test_planner_forwards_explicit_native_model_settings(tmp_path):
    from atbots.platform.session import AgentSession

    received = []

    def factory(*args, **kwargs):
        received.append(kwargs.get("model_settings"))
        return AgentSession(*args, **kwargs)

    settings = {"max_tokens": 1200}
    room = ControlRoom(
        AgentStore(tmp_path),
        model=TestModel(custom_output_text='{"action":"list"}'),
        model_settings=settings,
        session_factory=factory,
    )
    assert room.plan("List my agents").action == "list"
    assert received == [settings]
