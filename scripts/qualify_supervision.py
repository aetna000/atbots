"""Live native subscription CLI qualification in isolated AtSys workspaces.

No fixture executables, global service replacement, cloud deployment or API keys.
"""

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
    from atsys.cli import RUNTIME, node_executable

    node = node_executable()
    root = Path(tempfile.mkdtemp(prefix="atbots-live-supervision-"))
    data = root / "atsys"
    store = AgentStore(root / "agents")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = {**os.environ, "ATSYS_DATA_DIR": str(data), "ATSYS_PORT": str(port)}
    # Native CLIs reuse their own supported login; never copy credential files.
    client = AtSysClient(f"http://127.0.0.1:{port}")
    evidence = {
        "root": str(root),
        "fixture_only": False,
        "cloud_resources_created": False,
        "runs": [],
        "versions": {},
    }
    for provider in ("codex", "claude", "copilot"):
        result = subprocess.run(
            [provider, "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        evidence["versions"][provider] = (result.stdout or "unavailable").splitlines()[
            0
        ][:150]
    (root / "summary.json").write_text(json.dumps(evidence, indent=2))
    print(
        json.dumps(
            {"root": str(root), "phase": "starting isolated live CLI qualification"}
        ),
        flush=True,
    )
    daemon_pid = None
    pending = []
    with (root / "server.log").open("wb") as log:
        service = subprocess.Popen(
            [node, str(RUNTIME / "index.mjs")],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(80):
                try:
                    client.health()
                    break
                except RuntimeError:
                    time.sleep(0.25)
            doctor = client.request("/api/doctor")
            (root / "doctor.json").write_text(json.dumps(doctor, indent=2))
            for provider in ("codex", "claude", "copilot"):
                mixed = provider == "codex"
                name = provider + "-qualification"
                definition = store.create(name, limits=RunLimits(timeout_seconds=120))
                workspace = store.workspace(name) / "files"
                subprocess.run(["git", "init", "--quiet", str(workspace)], check=True)
                if mixed:
                    (workspace / "repair_target.txt").write_text("BROKEN")
                validator = "from pathlib import Path; assert Path('worker.txt').read_text().strip()=='WORKER_READY'"
                if mixed:
                    validator += "; assert Path('repair_target.txt').read_text().strip()=='FIXED', 'Controlled fault: repair_target.txt must contain FIXED'"
                objective = "Write exactly WORKER_READY to worker.txt in this workspace. Do not touch any other files."
                if mixed:
                    objective += " Do NOT modify repair_target.txt as the worker: it deliberately contains a controlled fault for a separate supervised repair. A repair role, if authorized by the supervisor, may change only repair_target.txt to exactly FIXED."
                contract = SupervisedObjective(
                    endpoint=client.endpoint,
                    worker=provider,
                    supervisor_provider="claude" if mixed else provider,
                    repair_provider="copilot" if mixed else provider,
                    trusted_local_execution=True,
                    allow_repair=mixed,
                    network_access=False,
                    validation_argv=[__import__("sys").executable, "-c", validator],
                    required_artifacts=["worker.txt"],
                    success_criteria=["Independent file-content validator passes"],
                    stages=["Inspect", "Write", "Validate"],
                    plan="Write the scoped fixture artifact. Validate independently. For the controlled mixed-runtime case, allow one scoped repair of repair_target.txt then retry. No unrelated changes, external messages, provisioning or credential access.",
                )
                submitted = client.submit(definition, workspace, objective, contract)
                identity = submitted["id"]
                pending.append(identity)
                link = Delegations(store).record(name, client.endpoint, submitted)
                print(
                    json.dumps(
                        {
                            "provider": provider,
                            "task_id": identity,
                            "state": "submitted",
                        }
                    ),
                    flush=True,
                )
                deadline = time.monotonic() + 400
                while time.monotonic() < deadline:
                    state = client.status(identity)
                    if state["status"] in {"completed", "stopped", "needs_attention"}:
                        break
                    time.sleep(1)
                row = {
                    "provider": provider,
                    "task_id": identity,
                    "delegation_id": link["id"],
                    "status": state["status"],
                    "mixed_runtime": mixed,
                    "role_providers": {
                        "worker": contract.worker,
                        "supervisor": contract.supervisor_provider,
                        "repair": contract.repair_provider,
                    },
                    "model_selection": "native CLI configured default; inspect provider receipts for available provenance",
                    "events": [e["type"] for e in state["events"]],
                    "attempts": [
                        {
                            "phase": a["phase"],
                            "provider": a.get("provider"),
                            "status": a.get("status"),
                        }
                        for a in state["attempts"]
                    ],
                }
                try:
                    row["report"] = client.report(identity)
                except RuntimeError:
                    row["report"] = None
                evidence["runs"].append(row)
                (root / "summary.json").write_text(json.dumps(evidence, indent=2))
                print(
                    json.dumps(
                        {
                            "provider": provider,
                            "task_id": identity,
                            "status": state["status"],
                            "report_present": bool(row["report"]),
                        }
                    ),
                    flush=True,
                )
                if state["status"] not in {"completed", "stopped", "needs_attention"}:
                    client.action(identity, "stop")
        finally:
            for identity in pending:
                try:
                    if client.status(identity)["status"] not in {
                        "completed",
                        "stopped",
                        "needs_attention",
                    }:
                        client.action(identity, "stop")
                except RuntimeError:
                    pass
            try:
                daemon_pid = (
                    client.request("/api/operations").get("daemon") or {}
                ).get("pid")
            except RuntimeError:
                pass
            service.terminate()
            try:
                service.wait(timeout=10)
            except subprocess.TimeoutExpired:
                service.kill()
                service.wait()
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
    print(
        json.dumps(
            {
                "root": str(root),
                "passed": sum(r["status"] == "completed" for r in evidence["runs"]),
                "total": len(evidence["runs"]),
            }
        )
    )


if __name__ == "__main__":
    main()
