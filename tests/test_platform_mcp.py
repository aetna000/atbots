import asyncio
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from atbots.platform.models import Capabilities
from atbots.platform.store import AgentStore


def test_real_mcp_browser_transport_scopes_and_native_image(tmp_path, monkeypatch):
    pytest.importorskip("mcp.server.mcpserver")
    pytest.importorskip("playwright")
    from pathlib import Path

    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[1] / "src"))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<title>MCP fixture</title><h1>Governed browser</h1>")

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    store = AgentStore(tmp_path)
    store.create("researcher")
    caps = Capabilities(
        browser_transport="mcp",
        browser_domains=["127.0.0.1"],
        browser_actions=["navigate", "snapshot", "screenshot"],
        vision=True,
    )
    transport = StdioTransport(
        command=sys.executable,
        env={
            "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
            "DEBUG": "pw:api",
        },
        log_file=tmp_path / "mcp-browser.stderr.log",
        args=[
            "-m",
            "atbots.platform.browser_mcp",
            "--profile",
            str(store.workspace("researcher") / "browser"),
            "--capabilities",
            caps.model_dump_json(),
        ],
        keep_alive=False,
    )

    async def check():
        import os

        if os.name == "posix" and Path("/dev/fd").exists():
            import resource

            print(
                "MCP resource preflight",
                len(os.listdir("/dev/fd")),
                resource.getrlimit(resource.RLIMIT_NOFILE),
            )
        async with Client(transport, init_timeout=30, timeout=90) as client:
            names = {tool.name for tool in await client.list_tools()}
            print("MCP stage: discovered")
            assert names == {
                "browser_navigate",
                "browser_snapshot",
                "browser_screenshot",
            }
            await client.call_tool(
                "browser_navigate", {"url": f"http://127.0.0.1:{server.server_port}"}
            )
            print("MCP stage: navigated")
            snapshot = await client.call_tool("browser_snapshot", {})
            assert "Governed browser" in str(snapshot.content)
            image = await client.call_tool("browser_screenshot", {})
            print("MCP stage: screenshot")
            assert (
                image.content[0].type == "image"
                and image.content[0].mime_type == "image/png"
            )
            denied = await client.call_tool(
                "browser_navigate", {"url": "https://example.com"}, raise_on_error=False
            )
            assert denied.is_error

    try:
        asyncio.run(check())
    finally:
        server.shutdown()
        server.server_close()


def test_mcp_discovery_does_not_launch_browser_and_tools_reuse_one_lifetime(
    tmp_path, monkeypatch
):
    pytest.importorskip("mcp.server.mcpserver")
    from fastmcp import Client

    import atbots.platform.browser_mcp as module

    events = []

    class Browser:
        def __init__(self, *args):
            pass

        async def __aenter__(self):
            events.append("started")
            return self

        async def __aexit__(self, *args):
            events.append("closed")

        async def browser_snapshot(self) -> str:
            return "fixture page"

        def tools(self):
            return [self.browser_snapshot]

    monkeypatch.setattr(module, "BrowserTools", Browser)
    app = module.server(tmp_path, Capabilities(browser_actions=["snapshot"]))

    async def check():
        async with Client(app) as client:
            assert await client.list_tools()
            assert events == []
            await client.call_tool("browser_snapshot", {})
            await client.call_tool("browser_snapshot", {})
            assert events == ["started"]

    asyncio.run(check())
    assert events == ["started", "closed"]


def test_granted_skills_are_discoverable_not_other_installed_bundles(tmp_path):
    from pydantic_ai.models.test import TestModel

    from atbots.platform.session import AgentSession
    from atbots.platform.skills import Skills

    store = AgentStore(tmp_path / "agents")
    store.create("researcher")
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("Use primary evidence.")
    skills = Skills(store.workspace("researcher") / "skills")
    digest = skills.review(str(source))["sha256"]
    skills.install("allowed", str(source), digest)
    skills.install("private", str(source), digest)
    store.configure(
        "researcher", expected_revision=1, capabilities={"skills": ["allowed"]}
    )
    session = AgentSession(
        store,
        "researcher",
        model=TestModel(call_tools=["available_skills"]),
        memory=None,
    )
    result = session.chat("List the skills I am permitted to use")
    assert result.requests >= 1
    _, history = store.history("researcher")
    assert b"available_skills" in history and b"allowed" in history
    from pydantic_ai.messages import ModelMessagesTypeAdapter, ToolReturnPart

    messages = ModelMessagesTypeAdapter.validate_json(history)
    catalogs = [
        part.content
        for message in messages
        for part in message.parts
        if isinstance(part, ToolReturnPart) and part.tool_name == "available_skills"
    ]
    assert catalogs and {row["name"] for row in catalogs[0]} == {"atsys", "allowed"}
