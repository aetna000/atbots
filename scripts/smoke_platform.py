"""Opt-in local-only installed-package acceptance; no paid model or cloud call."""

import argparse
import json
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from atbots.platform.control import ControlRoom
from atbots.platform.jobs import Operations
from atbots.platform.models import ModelBinding
from atbots.platform.session import AgentSession
from atbots.platform.store import AgentStore


def port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen3:4b-atbots-ctx8192")
    parser.add_argument("--atflows-source", type=Path)
    args = parser.parse_args()
    root = Path(tempfile.mkdtemp(prefix="atbots-platform-acceptance-"))
    store = AgentStore(root / "agents")
    binding = ModelBinding(model=args.model)
    store.create(
        "researcher",
        binding=binding,
        instructions="Follow the user's request exactly. /no_think",
    )
    ops = Operations(store)
    job = ops.submit("researcher", "Reply with exactly LOCAL_READY. /no_think")
    ops.launch(job["id"])
    deadline = time.monotonic() + 120
    while (
        ops.get(job["id"])["status"] in {"queued", "running"}
        and time.monotonic() < deadline
    ):
        time.sleep(0.5)
    job = ops.get(job["id"])
    if job["status"] != "replied" or "LOCAL_READY" not in job["result"]["answer"]:
        raise RuntimeError(
            "Installed background worker acceptance failed; inspect preserved root "
            + str(root)
        )
    report = {
        "root": str(root),
        "job_id": job["id"],
        "background_status": job["status"],
        "objective_verified": False,
    }
    store.create("control-room", binding=binding)
    room = ControlRoom(store)
    # Ensure the model receives current implementation instructions, not a
    # hand-written fixture schema or scripted dispatch result.
    from atbots.platform.control import MANAGEMENT_INSTRUCTIONS

    store.configure(
        "control-room", expected_revision=1, instructions=MANAGEMENT_INSTRUCTIONS
    )
    room = ControlRoom(store)
    plan = room.plan("Create a local agent named reviewer. /no_think")
    if plan.action != "create" or plan.name != "reviewer":
        raise RuntimeError("Live intent routing failed; preserved root " + str(root))
    proposal = room.dispatch(plan)
    report["live_intent_created"] = room.approve(proposal["approval_required"])[
        "applied"
    ]["name"]
    if args.atflows_source:
        import os

        bun = shutil.which("bun")
        if not bun:
            raise RuntimeError(
                "AtFlows fixture needs existing Bun; no runtime was downloaded"
            )
        source = args.atflows_source.resolve(strict=True)
        proxy, dashboard = port(), port()
        data = root / "atflows"
        env = {
            **os.environ,
            "DATA_DIR": str(data),
            "PROXY_PORT": str(proxy),
            "DASHBOARD_PORT": str(dashboard),
            "OLLAMA_HOST": "127.0.0.1",
        }
        env.pop("ATFLOWS_ATMEM_AUTH_URL", None)
        env.pop("ATFLOWS_ADMIN_PASSWORD", None)
        with (root / "atflows.log").open("wb") as log:
            process = subprocess.Popen(
                [bun, "run", "apps/server/src/server.ts"],
                cwd=source,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                ready = False
                for _ in range(60):
                    try:
                        with urlopen(
                            f"http://127.0.0.1:{dashboard}/api/health", timeout=0.5
                        ) as response:
                            ready = json.load(response).get("status") == "ok"
                        if ready:
                            break
                    except OSError:
                        time.sleep(0.25)
                if not ready:
                    raise RuntimeError(
                        "Isolated AtFlows startup failed; inspect preserved private log"
                    )
                store.create(
                    "traced",
                    binding=ModelBinding(
                        kind="openai-compatible",
                        model=args.model,
                        endpoint=f"http://127.0.0.1:{proxy}/ollama",
                    ),
                )
                result = AgentSession(store, "traced").chat(
                    "Reply exactly TRACE_READY. /no_think"
                )
                if "TRACE_READY" not in result.text:
                    raise RuntimeError("Proxy model reply failed")
                with sqlite3.connect(data / "data.db") as db:
                    row = db.execute(
                        "SELECT COUNT(*),SUM(prompt_tokens),SUM(completion_tokens) FROM traces WHERE model=?",
                        (args.model,),
                    ).fetchone()
                report["atflows"] = {
                    "model": args.model,
                    "traces": row[0],
                    "input_tokens": row[1],
                    "output_tokens": row[2],
                }
                if not row[0]:
                    raise RuntimeError("AtFlows did not persist its model trace")
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    (root / "summary.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
