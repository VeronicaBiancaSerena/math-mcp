"""Local MCP stdio client smoke script.

Run with::

    python examples/mcp_client_smoke.py
"""

import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "math_mcp"],
    )

    async with (
        stdio_client(server_params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()

        tools = await session.list_tools()
        print("tools:", [tool.name for tool in tools.tools])

        capabilities = await session.call_tool("math_capabilities", {})
        print("public tools:", list(capabilities.structuredContent["public_tools"]))

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
        print("simplify result:", result.structuredContent["result"])


if __name__ == "__main__":
    asyncio.run(main())
