from __future__ import annotations

from pathlib import Path

from atbots.config import AtBotConfig
from atbots.gateway import AtMemGateway
from atbots.runtime import AtBotRuntime
from atbots.agent import TaskAgent
from atbots.companion import CompanionRuntime


def config_for(path: Path) -> AtBotConfig:
    return AtBotConfig(memory_path=str(path), providers=[])


def test_initialize_always_creates_vector_store(tmp_path: Path) -> None:
    config = config_for(tmp_path / "memory.db")
    result = AtMemGateway(config).initialize()
    assert Path(config.memory_path).is_file()
    assert (tmp_path / "memory.db.vectors.db").is_file()
    assert result["capabilities"]["features"]["default_local_vectors"] is True


def test_automatic_inference_recall_and_exposure(tmp_path: Path) -> None:
    runtime = AtBotRuntime(config_for(tmp_path / "memory.db"))
    admissions = runtime.remember("I prefer concise technical answers")
    assert admissions[0]["decision"] == "active"

    candidates = runtime.recall("concise technical answers")
    assert candidates.candidates[0].content == "I prefer concise technical answers"

    result = runtime.chat("Do I prefer concise technical answers?")
    assert "governed memory" in result.text
    assert result.memory_record_ids
    assert result.context_receipt_id
    assert result.cache_key.startswith("atbot-prompt-v1:")
    assert all("content" not in row for row in result.trace)


def test_question_is_not_silently_stored(tmp_path: Path) -> None:
    runtime = AtBotRuntime(config_for(tmp_path / "memory.db"))
    assert runtime.remember("What is my favorite city?") == ()
    assert AtMemGateway(runtime.config).inspect_records() == []


def test_relevance_gate_rejects_unrelated_memory_but_allows_overview(tmp_path: Path) -> None:
    runtime = AtBotRuntime(config_for(tmp_path / "memory.db"))
    runtime.remember("I prefer concise technical answers")
    assert runtime.recall("what is my opinion about cars?").candidates == ()
    overview = runtime.recall("What do you remember about me?")
    assert len(overview.candidates) == 1
    absent = runtime.chat("what is my opinion about cars?")
    assert absent.text == "I don't have a governed memory of that yet."
    assert absent.memory_record_ids == ()
    summary = runtime.chat("What do you remember about me?")
    assert summary.text == "I remember:\n- I prefer concise technical answers"
    assert len(summary.memory_record_ids) == 1


def test_task_agent_is_bounded_and_has_explicit_tools(tmp_path: Path) -> None:
    config = config_for(tmp_path / "memory.db")
    agent = TaskAgent(config)
    assert agent.tools.descriptions()[0]["name"] == "memory_recall"
    result = agent.run("Summarize what you remember")
    assert result.status == "completed"
    assert result.steps == 1
    assert result.trace[0]["tool"] == "memory_recall"
    assert result.trace[1]["action"] == "finish"


def test_public_companion_has_no_independent_agent_or_storage(tmp_path: Path) -> None:
    companion = CompanionRuntime(config_for(tmp_path / "unused.db"))
    capabilities = companion.capabilities()
    assert capabilities["role"] == "atmem-intelligence-companion"
    assert capabilities["independent_agent"] is False
    assert capabilities["canonical_storage"] is False


def test_companion_ranks_only_ids_supplied_by_atmem(tmp_path: Path) -> None:
    companion = CompanionRuntime(config_for(tmp_path / "unused.db"))
    result = companion.answer_query(
        query="What do you remember about me?",
        candidates=[{"record_id": "rec_allowed", "content": "User likes blue cars."}],
    )
    assert result["ranked_record_ids"] == ["rec_allowed"]
    assert "blue cars" in result["answer"]


def test_companion_overview_removes_source_template_noise(tmp_path: Path) -> None:
    companion = CompanionRuntime(config_for(tmp_path / "unused.db"))
    result = companion.answer_query(
        query="What do you remember about me?",
        candidates=[
            {"record_id": "rec_fact", "content": "JT likes burgers."},
            {"record_id": "rec_heading", "content": "# USER.md - About Your Human."},
            {"record_id": "rec_template", "content": "Learn about the person you're helping. Update this as you go."},
        ],
    )
    assert result["ranked_record_ids"] == ["rec_fact"]
    assert "USER.md" not in result["answer"]


def test_query_expansion_is_content_free_and_bounded(tmp_path: Path) -> None:
    companion = CompanionRuntime(config_for(tmp_path / "unused.db"))
    result = companion.expand_query("what is my fav food")
    assert result["content_received"] is False
    assert "food preference" in result["expanded_queries"]
    assert len(result["expanded_queries"]) <= 6


def test_companion_proposes_but_never_admits_or_stores(tmp_path: Path) -> None:
    memory_path = tmp_path / "must-not-exist.db"
    companion = CompanionRuntime(config_for(memory_path))

    result = companion.propose_memories("I prefer window seats")

    assert result["format"] == "atbot-memory-proposals-v1"
    assert result["proposals"][0]["fact"] == "I prefer window seats"
    assert result["authority_decision"] is None
    assert result["canonical_storage"] is False
    assert result["proposals"][0]["related_record_ids"] == []
    assert not memory_path.exists()


def test_companion_does_not_propose_questions(tmp_path: Path) -> None:
    companion = CompanionRuntime(config_for(tmp_path / "unused.db"))
    result = companion.propose_memories("What food do I prefer?")
    assert result["proposals"] == []
