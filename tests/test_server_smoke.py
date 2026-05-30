"""Real MCP stdio smoke test: start the server as a subprocess and call tools."""

from __future__ import annotations

import os
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
@pytest.mark.mcp
async def test_mcp_ping_and_simplify() -> None:
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "math_mcp"],
        env=dict(os.environ),
    )

    async with (
        stdio_client(server_params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()

        tools = await session.list_tools()
        names = {tool.name for tool in tools.tools}
        assert "ping" in names
        assert "math_capabilities" in names
        assert "algebra_compute" in names
        assert len(names) == 18

        result = await session.call_tool(
            "algebra_compute",
            {
                "operation": "simplify_expression",
                "payload": {
                    "expression": "sin(x)**2 + cos(x)**2 - 1",
                    "variables": ["x"],
                },
            },
        )

        assert result.isError is False
        assert result.structuredContent is not None
        assert result.structuredContent["result"] == "0"
        assert result.structuredContent["certainty"] == "exact"


@pytest.mark.asyncio
@pytest.mark.mcp
async def test_mcp_capabilities_lists_public_tools() -> None:
    server_params = StdioServerParameters(
        command=sys.executable, args=["-m", "math_mcp"], env=dict(os.environ)
    )
    async with (
        stdio_client(server_params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        cap = await session.call_tool("math_capabilities", {})
        assert cap.structuredContent is not None
        public_tools = cap.structuredContent["public_tools"]
        assert "matrix_compute" in public_tools
        assert public_tools["ping"]["kind"] == "utility"
