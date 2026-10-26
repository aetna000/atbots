import json

from cryptography.fernet import Fernet

from atbots.cli import main
from atbots.platform.store import AgentStore


def test_operator_commands_and_encrypted_restore(tmp_path, monkeypatch, capsys):
    root = tmp_path / "source"
    store = AgentStore(root)
    store.create("researcher")
    prefix = ["--root", str(root)]
    assert main(prefix + ["doctor"]) == 0
    assert json.loads(capsys.readouterr().out)["model_inference_tested"] is False
    assert main(prefix + ["jobs", "submit", "researcher", "Write a report"]) == 0
    job = json.loads(capsys.readouterr().out)
    assert job["status"] == "queued"
    assert main(prefix + ["jobs", "cancel", job["id"]]) == 0
    capsys.readouterr()
    monkeypatch.setenv("FIXTURE_ARCHIVE_KEY", Fernet.generate_key().decode())
    archive = tmp_path / "agent.encrypted"
    assert (
        main(
            prefix
            + [
                "state",
                "export",
                str(archive),
                "--name",
                "researcher",
                "--key-env",
                "FIXTURE_ARCHIVE_KEY",
            ]
        )
        == 0
    )
    capsys.readouterr()
    restored = tmp_path / "destination"
    assert (
        main(
            [
                "--root",
                str(restored),
                "state",
                "import",
                str(archive),
                "--key-env",
                "FIXTURE_ARCHIVE_KEY",
            ]
        )
        == 0
    )
    assert AgentStore(restored).get("researcher").id == store.get("researcher").id


def test_mandatory_explicit_cloud_grants(tmp_path):
    import pytest

    from atbots.platform.deployment import build_container

    wheel = tmp_path / "candidate.whl"
    wheel.write_bytes(b"fixture")
    with pytest.raises(ValueError):
        build_container(wheel, "image:latest", "python:latest")
