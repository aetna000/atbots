"""Upstream MCP transport for the same governed Playwright browser capabilities.

No public listener, arbitrary server command, or second browser policy engine.
"""

import argparse
import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from functools import wraps
from pathlib import Path

from atbots.platform.browser import BrowserTools
from atbots.platform.models import Capabilities


def server(profile, capabilities):
    from mcp.server.mcpserver import Image, MCPServer

    browser = BrowserTools(profile, capabilities)
    stack = AsyncExitStack()
    start_lock = asyncio.Lock()
    started = False

    @asynccontextmanager
    async def lifetime(_server):
        nonlocal started
        async with stack:
            try:
                yield {}
            finally:
                started = False

    async def ensure_started():
        nonlocal started
        async with start_lock:
            if not started:
                await stack.enter_async_context(browser)
                started = True

    def deferred(method):
        @wraps(method)
        async def invoke(*args, **kwargs):
            await ensure_started()
            return await method(*args, **kwargs)

        return invoke

    app = MCPServer("AtBots scoped browser", lifespan=lifetime, log_level="ERROR")
    for method in browser.tools():
        if method.__name__ != "browser_screenshot":
            app.tool()(deferred(method))

    if "screenshot" in capabilities.browser_actions and capabilities.vision:

        @app.tool()
        async def browser_screenshot() -> Image:
            """Return the current permitted page as native PNG image content."""
            await ensure_started()
            result = await browser.browser_screenshot()
            return Image(data=result.content[0].data, format="png")

    return app


def toolset(profile, capabilities):
    import sys

    from fastmcp.client.transports import StdioTransport
    from pydantic_ai.mcp import MCPToolset

    transport = StdioTransport(
        command=sys.executable,
        env={"PYTHONPATH": str(Path(__file__).resolve().parents[2])},
        args=[
            "-m",
            "atbots.platform.browser_mcp",
            "--profile",
            str(profile),
            "--capabilities",
            capabilities.model_dump_json(),
        ],
        keep_alive=False,
    )
    return MCPToolset(
        transport,
        init_timeout=30,
        # Cold Chrome startup/cleanup has a separate budget from discovery.
        # The enclosing agent turn still enforces its overall deadline.
        read_timeout=90,
        tool_error_behavior="error",
        include_instructions=False,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--capabilities", required=True)
    args = parser.parse_args()
    caps = Capabilities.model_validate_json(args.capabilities)
    server(args.profile, caps).run(transport="stdio")


if __name__ == "__main__":
    main()
