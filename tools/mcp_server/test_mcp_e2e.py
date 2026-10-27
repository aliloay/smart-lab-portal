"""End-to-end MCP check (2026-10-27): a real MCP client (official SDK) starts tools/mcp_server/server.py over stdio and
lists / calls the lab tools against a running portal (default: the isolated test copy on 127.0.0.1:8100).
    set SMARTLAB_URL=http://127.0.0.1:8100 & set SMARTLAB_TOKEN=<staff token>
    tools/mcp_server/.venv/Scripts/python tools/mcp_server/test_mcp_e2e.py
"""
import asyncio
import os
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = os.path.dirname(os.path.abspath(__file__))


async def main() -> int:
    params = StdioServerParameters(command=sys.executable, args=[os.path.join(HERE, "server.py")],
                                   env={**os.environ})
    fails = 0

    def check(ok, what):
        nonlocal fails
        print(("PASS " if ok else "FAIL ") + what)
        fails += not ok
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            t0 = time.perf_counter()
            tools = (await s.list_tools()).tools
            names = {t.name for t in tools}
            check(len(tools) >= 9 and "get_environment" in names, f"list_tools: {len(tools)} tools ({(time.perf_counter() - t0) * 1000:.0f} ms)")
            check(all(t.annotations and t.annotations.read_only_hint for t in tools), "every tool is marked read-only")
            check(not any(k in n for n in names for k in ("unlock", "relay", "move", "door_open")), "no physical-action tool")
            ts = next(t for t in tools if t.name == "get_trends").input_schema
            check(ts["properties"]["weeks"]["maximum"] == 52, "typed schema with ranges")
            t0 = time.perf_counter()
            res = await s.call_tool("list_labs", {})
            check(not res.is_error and "[ok]" in res.content[0].text, f"call list_labs ({(time.perf_counter() - t0) * 1000:.0f} ms)")
            res = await s.call_tool("get_report", {"period": "weekly"})
            check(not res.is_error, "call get_report weekly")
            res = await s.call_tool("get_trends", {"weeks": 999})
            check(res.is_error and "between 2 and 52" in res.content[0].text, "out-of-range argument refused")
            res = await s.call_tool("unlock_door", {})
            check(res.is_error and "not allowed" in res.content[0].text, "unlock_door refused")
    print("MCP e2e:", "ALL PASS" if not fails else f"{fails} FAILED")
    return fails


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
