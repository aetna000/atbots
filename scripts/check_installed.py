"""Offline installed-artifact smoke check; never uses real provider credentials."""

import importlib.metadata
import importlib.resources
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from pydantic_ai.models.test import TestModel

import atbots
from atbots.platform.session import AgentSession
from atbots.platform.store import AgentStore

assert atbots.__version__ == importlib.metadata.version("atbots") == "0.3.0b2"
assert "site-packages" in str(Path(atbots.__file__).resolve()), atbots.__file__
resources = importlib.resources.files("atbots.platform")
assert "Work and outcomes" in resources.joinpath("control-room.html").read_text()
assert resources.joinpath("container.Dockerfile").is_file()
for name in ("control-room.js", "control-room.css", "atsys-skill.md"):
    assert resources.joinpath(name).is_file(), name
version = subprocess.run([sys.executable, "-m", "atbots.cli", "--version"],
                         check=True, text=True, capture_output=True)
assert "0.3.0b2" in version.stdout
with tempfile.TemporaryDirectory(prefix="atbots-installed-") as directory:
    store = AgentStore(Path(directory) / "platform")
    definition = store.create("release-check")
    session = AgentSession(
        store, definition.name, model=TestModel(custom_output_text="READY")
    )
    assert session.chat("Offline release check").text == "READY"
    result = subprocess.run(
        [
            str(Path(sys.executable).with_name("atbots")),
            "--root",
            str(store.root),
            "agents",
            "list",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    assert any(agent["name"] == definition.name for agent in json.loads(result.stdout))
print(
    "Installed AtBots beta: version, bundled resources, native test-model session and CLI passed."
)
