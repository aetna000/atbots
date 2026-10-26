"""Bounded production-session browser qualification. No API/model inference calls."""

import argparse
import json
import tempfile
import threading
import time
from contextlib import nullcontext
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pydantic_ai.messages import (
    ModelMessagesTypeAdapter,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import FunctionModel

from atbots.platform.models import RunLimits
from atbots.platform.session import AgentSession
from atbots.platform.store import AgentStore


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=5, choices=range(1, 11))
    args = parser.parse_args()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(
                b"<title>AtBots transport fixture</title><h1>Scoped fixture evidence</h1>"
            )

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    results = []
    try:
        with nullcontext(tempfile.mkdtemp(prefix="atbots-mcp-stability-")) as root:
            print(json.dumps({"evidence_root": root, "retained": True}), flush=True)
            store = AgentStore(root)
            for index in range(args.runs):
                name = f"browser-{index}"
                store.create(name, limits=RunLimits(requests=6, timeout_seconds=120))
                store.configure(
                    name,
                    expected_revision=1,
                    capabilities={
                        "browser_transport": "mcp",
                        "browser_domains": ["127.0.0.1"],
                        "browser_actions": ["navigate", "snapshot", "screenshot"],
                        "vision": True,
                    },
                )
                sequence = [
                    (
                        "browser_navigate",
                        {"url": f"http://127.0.0.1:{server.server_port}"},
                    ),
                    ("browser_snapshot", {}),
                    ("browser_screenshot", {}),
                ]
                calls = 0

                def model(messages, info, moves=tuple(sequence)):
                    nonlocal calls
                    if calls < len(moves):
                        tool, arguments = moves[calls]
                        calls += 1
                        return ModelResponse(parts=[ToolCallPart(tool, arguments)])
                    return ModelResponse(parts=[TextPart("Fixture inspected")])

                started = time.monotonic()
                print(
                    json.dumps(
                        {
                            "iteration": index + 1,
                            "status": "starting",
                            "api_inference": False,
                        }
                    ),
                    flush=True,
                )
                try:
                    result = AgentSession(store, name, model=FunctionModel(model)).chat(
                        "Inspect only the permitted fixture page, including a screenshot."
                    )
                    messages = ModelMessagesTypeAdapter.validate_json(
                        store.history(name)[1]
                    )
                    snapshot = [
                        p
                        for message in messages
                        for p in message.parts
                        if isinstance(p, ToolReturnPart)
                        and p.tool_name == "browser_snapshot"
                    ]
                    passed = result.requests == 4 and any(
                        "Scoped fixture evidence" in str(p.content) for p in snapshot
                    )
                    row = {
                        "iteration": index + 1,
                        "passed": passed,
                        "requests": result.requests,
                        "elapsed_seconds": round(time.monotonic() - started, 2),
                    }
                except Exception:  # noqa: BLE001 - print only sanitized recorded failure class
                    row = {
                        "iteration": index + 1,
                        "passed": False,
                        "elapsed_seconds": round(time.monotonic() - started, 2),
                        "receipt": store.receipts(name)[-1],
                    }
                results.append(row)
                print(json.dumps(row), flush=True)
    finally:
        server.shutdown()
        server.server_close()
    print(
        json.dumps(
            {
                "runs": len(results),
                "passed": sum(r["passed"] for r in results),
                "api_inference": False,
            }
        ),
        flush=True,
    )
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
