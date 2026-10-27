"""
Smart Lab MCP server (2026-10-27) - the lab's READ-ONLY tools for any local MCP client (e.g. Claude Desktop, an IDE).

A thin front built on the official MCP Python SDK (low-level Server, stdio transport - no network port is opened).
The tool list and every call go to the portal's own gateway (/api/ai/tools), which validates the arguments against
typed schemas, checks the caller's role (staff / admin token), enforces a timeout and writes every call to the audit
log. The portal never depends on this process: if it is not running, nothing in the portal changes.

Nothing here can unlock a door, switch a relay or move a robot: those are not tools, and the gateway refuses them by name.

Setup (once): py -m venv tools/mcp_server/.venv && tools/mcp_server/.venv/Scripts/python -m pip install mcp
Run:          set SMARTLAB_URL=http://127.0.0.1   &   set SMARTLAB_TOKEN=<a staff access token>
              tools/mcp_server/.venv/Scripts/python tools/mcp_server/server.py
"""
from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

BASE = os.environ.get("SMARTLAB_URL", "http://127.0.0.1").rstrip("/") + "/api/ai/tools"
TOKEN = os.environ.get("SMARTLAB_TOKEN", "")
TIMEOUT_S = 15


def _req(method: str, url: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=TIMEOUT_S) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read()).get("detail")
        except ValueError:
            detail = None
        return e.code, {"status": "refused", "result": detail or f"HTTP {e.code}"}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 0, {"status": "unavailable", "result": f"the Smart Lab portal is not reachable ({e})"}


async def list_tools(ctx, params) -> types.ListToolsResult:
    code, body = await asyncio.to_thread(_req, "GET", BASE)
    tools = [types.Tool(name=t["name"], description=t["description"], inputSchema=t["input_schema"],
                        annotations=types.ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False))
             for t in body.get("tools", [])]
    return types.ListToolsResult(tools=tools)


async def call_tool(ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
    code, body = await asyncio.to_thread(_req, "POST", f"{BASE}/{params.name}",
                                         {"arguments": params.arguments or {}, "via": "mcp"})
    ok = code == 200 and body.get("status") == "ok"
    text = body.get("result") if isinstance(body.get("result"), str) else json.dumps(body.get("result"))
    return types.CallToolResult(content=[types.TextContent(type="text", text=f"[{body.get('status')}] {text}")],
                                isError=not ok)


server = Server("smart-lab", version="1.0",
                instructions="Read-only Smart Lab monitoring tools (labs, operations, trends, reports, maintenance, "
                             "anomalies, readiness, environment). No physical control.",
                on_list_tools=list_tools, on_call_tool=call_tool)


async def main() -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
