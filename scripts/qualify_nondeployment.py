"""Bounded opt-in API vision and intent acceptance; no cloud provisioning.

Credentials are read only from an explicitly selected env file/environment.
Evidence contains fixture data/model IDs/usage, never keys or raw SDK errors.
"""

import argparse
import json
import os
import secrets
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from atbots.platform.control import MANAGEMENT_INSTRUCTIONS, ControlRoom
from atbots.platform.models import ModelBinding, RunLimits
from atbots.platform.session import AgentSession
from atbots.platform.store import AgentStore


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--model", default="gpt-5.4-nano")
    parser.add_argument("--endpoint", default="https://api.openai.com/v1")
    parser.add_argument("--key-env", default="OPENAI_API_KEY")
    parser.add_argument("--vision", action="store_true")
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--reasoning-effort", choices=("none", "low", "medium", "high"))
    parser.add_argument("--intents", action="store_true")
    parser.add_argument(
        "--cases", type=Path, default=Path("evals/platform-intents-v1.json")
    )
    parser.add_argument("--limit", type=int, default=19)
    args = parser.parse_args()
    if args.env_file:
        from dotenv import dotenv_values

        value = dotenv_values(args.env_file).get(args.key_env)
        if value:
            os.environ[args.key_env] = value
    if not args.local and not os.environ.get(args.key_env):
        raise RuntimeError("Selected API credential reference is unavailable")
    if not 1 <= args.limit <= 30:
        raise ValueError("Intent limit must be 1–30")
    os.environ["PYDANTIC_AI_NO_BANNER"] = "1"
    root = Path(tempfile.mkdtemp(prefix="atbots-nondeploy-live-"))
    binding = ModelBinding(
        kind="ollama" if args.local else "openai-compatible",
        model=args.model,
        endpoint=args.endpoint,
        api_key_env=None if args.local else args.key_env,
        egress_class="local" if args.local else "remote",
    )
    evidence = {
        "root": str(root),
        "model": args.model,
        "cloud_resources_created": False,
        "provider_usage": [],
        "local_inference": args.local,
        "reasoning_effort": args.reasoning_effort
        or (None if args.local else "none" if args.vision else "low"),
        "vision": None,
        "intents": [],
    }
    settings = {"max_tokens": 1200}
    if not args.local:
        # The selected nano model permits Chat Completions function tools only
        # with reasoning disabled. This is a qualification setting, not a
        # silent change to any user's persisted model configuration.
        settings["extra_body"] = {"reasoning_effort": "none" if args.vision else "low"}
    if args.reasoning_effort is not None:
        settings["extra_body"] = {"reasoning_effort": args.reasoning_effort}
    if args.vision:
        code = secrets.token_hex(3).upper()

        class Fixture(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    (
                        "<title>AtBots visual fixture</title><canvas id='badge' width='640' height='240'></canvas><script>const c=document.getElementById('badge').getContext('2d');c.fillStyle='#ffffff';c.fillRect(0,0,640,240);c.fillStyle='#172725';c.font='64px monospace';c.fillText('"
                        + code
                        + "',60,140);</script>"
                    ).encode()
                )

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            for transport in ("native", "mcp"):
                store = AgentStore(root / transport)
                definition = store.create(
                    "visual",
                    binding=binding,
                    remote_allowed=True,
                    limits=RunLimits(
                        requests=5, total_tokens=10000, timeout_seconds=90
                    ),
                )
                store.configure(
                    "visual",
                    expected_revision=definition.revision,
                    capabilities={
                        "browser_transport": transport,
                        "browser_domains": ["127.0.0.1"],
                        "browser_actions": ["navigate", "screenshot"],
                        "vision": True,
                    },
                )
                result = AgentSession(store, "visual", model_settings=settings).chat(
                    f"Navigate to http://127.0.0.1:{server.server_port}, take a screenshot, and return exactly the six-character hexadecimal code visibly drawn there. Use the tools; do not guess.",
                    sensitivity="public",
                )
                passed = result.text.strip() == code
                evidence.setdefault("vision_results", []).append(
                    {
                        "transport": transport,
                        "passed": passed,
                        "requests": result.requests,
                    }
                )
                evidence["provider_usage"].append(
                    {
                        "model": result.model,
                        "input_tokens": result.input_tokens,
                        "output_tokens": result.output_tokens,
                        "cost_usd": None,
                    }
                )
                if not passed:
                    raise RuntimeError(
                        "Vision fixture code did not match; inspect preserved local root"
                    )
            evidence["vision"] = True
        finally:
            server.shutdown()
            server.server_close()
    if args.intents:
        cases = json.loads(args.cases.read_text())["cases"][: args.limit]
        for index, case in enumerate(cases):
            store = AgentStore(root / f"intent-{index:02d}")
            initial_agents = case.get("initial_agents", ["researcher", "reviewer"])
            for name in initial_agents:
                store.create(name)
            store.create(
                "control-room",
                binding=binding,
                remote_allowed=True,
                instructions=MANAGEMENT_INSTRUCTIONS,
                limits=RunLimits(requests=2, total_tokens=12000, timeout_seconds=60),
            )
            room = ControlRoom(store, model_settings=settings)
            try:
                plan = room.plan(case["text"])
                keys = set(case["expected"]) - {"message"}
                expected = case["expected"]
                passed = all(getattr(plan, key) == expected[key] for key in keys)
                # No grant can be manufactured even when the requested family
                # is otherwise correct. This campaign never approves a plan.
                passed = passed and plan.remote_allowed is not True
                evidence["intents"].append(
                    {
                        "text": case["text"],
                        "initial_agents": initial_agents,
                        "expected": expected,
                        "actual": plan.model_dump(mode="json"),
                        "passed": passed,
                    }
                )
                receipt = store.receipts("control-room")[-1]
                evidence["provider_usage"].append(
                    {
                        key: receipt[key]
                        for key in ("model", "input_tokens", "output_tokens", "cost")
                    }
                )
            except RuntimeError as exc:
                evidence["intents"].append(
                    {
                        "text": case["text"],
                        "passed": False,
                        "failure_type": type(exc).__name__,
                    }
                )
            (root / "summary.json").write_text(json.dumps(evidence, indent=2))
    evidence["intent_passed"] = sum(row["passed"] for row in evidence["intents"])
    evidence["intent_total"] = len(evidence["intents"])
    (root / "summary.json").write_text(json.dumps(evidence, indent=2))
    print(
        json.dumps(
            {
                key: value
                for key, value in evidence.items()
                if key not in {"intents", "provider_usage"}
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
