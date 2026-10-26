"""Real installed AtSys HTTP/recovery test using upstream CLI fixtures, no LLMs.

This verifies adapter transport and execution ownership, not live provider quality.
"""

import argparse
import json
import os
import signal
import socket
import subprocess
import tempfile
import time
from pathlib import Path

from atbots.platform.integrations import AtSysClient, Delegations, SupervisedObjective
from atbots.platform.models import RunLimits
from atbots.platform.store import AgentStore


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--atsys-source", type=Path, required=True)
    args = parser.parse_args()
    from atsys.cli import RUNTIME, node_executable

    node = node_executable()
    root = Path(tempfile.mkdtemp(prefix="atbots-supervision-acceptance-"))
    binary = root / "bin"
    binary.mkdir()
    fixture = (args.atsys_source / "tests/fixtures/provider-cli.cjs").read_text()
    for provider in ("codex", "claude", "copilot"):
        path = binary / provider
        path.write_text("#!" + node + "\n" + fixture)
        path.chmod(0o700)
    store = AgentStore(root / "agents")
    definition = store.create("researcher", limits=RunLimits(timeout_seconds=60))
    workspace = store.workspace("researcher") / "files"
    (workspace / "fixture-mode.json").write_text('{"recovery":true}')
    data = root / "atsys"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = {
        **os.environ,
        "ATSYS_DATA_DIR": str(data),
        "ATSYS_PORT": str(port),
        "PATH": str(binary) + os.pathsep + os.environ.get("PATH", ""),
    }
    client = AtSysClient(f"http://127.0.0.1:{port}")
    task_id = None
    daemon_pid = None
    with (root / "server.log").open("wb") as log:
        process = subprocess.Popen(
            [node, str(RUNTIME / "index.mjs")],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            ready = False
            for _ in range(80):
                try:
                    client.health()
                    ready = True
                    break
                except RuntimeError:
                    time.sleep(0.25)
            if not ready:
                raise RuntimeError(
                    "Isolated AtSys service did not start; preserved root " + str(root)
                )
            contract = SupervisedObjective(
                endpoint=client.endpoint,
                worker="copilot",
                supervisor_provider="claude",
                repair_provider="codex",
                trusted_local_execution=True,
                allow_repair=True,
                validation_argv=[
                    node,
                    "-e",
                    "const fs=require('fs');process.exit(fs.readFileSync('feature.txt','utf8')==='implemented'?0:1)",
                ],
                required_artifacts=["feature.txt"],
                success_criteria=["feature.txt contains implemented"],
                stages=["Inspect", "Implement", "Check"],
                plan="Exercise a controlled upstream fixture failure, diagnose, repair and independently check the scoped artifact. No paid model calls.",
            )
            result = client.submit(
                definition,
                workspace,
                "Implement the upstream fixture feature with independent acceptance",
                contract,
            )
            task_id = result["id"]
            link = Delegations(store).record("researcher", client.endpoint, result)
            deadline = time.monotonic() + 100
            while time.monotonic() < deadline:
                state = client.status(task_id)
                if state["status"] in {"completed", "stopped", "needs_attention"}:
                    break
                time.sleep(0.5)
            daemon = client.request("/api/operations").get("daemon") or {}
            daemon_pid = daemon.get("pid")
            if state["status"] != "completed":
                raise RuntimeError(
                    "Fixture recovery not accepted; inspect preserved root " + str(root)
                )
            report = client.report(task_id)
            summary = {
                "root": str(root),
                "task_id": task_id,
                "status": state["status"],
                "delegation_id": link["id"],
                "providers": {
                    "worker": "copilot",
                    "supervisor": "claude",
                    "repair": "codex",
                },
                "attempts": len(state["attempts"]),
                "report_present": bool(report),
                "fixture_only": True,
                "paid_model_calls": 0,
                "events": [e["type"] for e in state["events"]],
            }
            (root / "summary.json").write_text(json.dumps(summary, indent=2))
            print(json.dumps(summary, indent=2))
        finally:
            if task_id:
                try:
                    if client.status(task_id)["status"] not in {
                        "completed",
                        "stopped",
                        "needs_attention",
                    }:
                        client.action(task_id, "stop")
                    daemon_pid = daemon_pid or (
                        client.request("/api/operations").get("daemon") or {}
                    ).get("pid")
                except RuntimeError:
                    pass
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            if daemon_pid:
                command = subprocess.run(
                    ["ps", "-p", str(daemon_pid), "-o", "command="],
                    capture_output=True,
                    text=True,
                    check=False,
                ).stdout
                if str(data) in command:
                    try:
                        os.kill(daemon_pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass


if __name__ == "__main__":
    main()
