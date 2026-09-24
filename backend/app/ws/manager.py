"""
WebSocket fan-out for the live activity stream and in-portal notifications.

Every socket belongs to an authenticated user. What a socket receives depends
on who that is:

  * staff and admins receive every access event (optionally one lab only);
  * a student receives only access events about themselves - the same rule
    the REST endpoints enforce, so the live channel cannot become a side door
    around it;
  * notifications go only to the person they are addressed to.

Sends are best-effort. The source of truth is the database; a client that
drops and reconnects refetches.

Thread safety: FastAPI runs synchronous endpoints in a worker thread pool,
where there is no running event loop. Publishing therefore goes through the
loop captured at startup with run_coroutine_threadsafe - calling
asyncio.get_running_loop() from a worker thread raises, which is exactly how
the previous implementation silently dropped every live event.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import WebSocket


@dataclass
class Client:
    user_id: int
    is_staff: bool
    lab_filter: Optional[int]


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: dict[WebSocket, Client] = {}
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    async def connect(self, ws: WebSocket, client: Client) -> None:
        await ws.accept()
        self._clients[ws] = client

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.pop(ws, None)

    # --------------------------------------------------------------- routing
    def _wants(self, client: Client, message: dict[str, Any]) -> bool:
        kind = message.get("type")
        if kind == "notification":
            return message.get("user_id") == client.user_id
        if kind == "access_event":
            ev = message.get("event", {})
            if client.lab_filter is not None and ev.get("lab_id") != client.lab_filter:
                return False
            return client.is_staff or ev.get("user_id") == client.user_id
        if kind == "staff":
            return client.is_staff
        return False

    async def _send(self, message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws, client in list(self._clients.items()):
            if not self._wants(client, message):
                continue
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def publish(self, message: dict[str, Any]) -> None:
        """Schedule a send from any thread. Never raises."""
        loop = self.loop
        if loop is None or loop.is_closed() or not self._clients:
            return
        try:
            try:
                running = asyncio.get_running_loop()
            except RuntimeError:
                running = None
            if running is loop:
                loop.create_task(self._send(message))
            else:
                asyncio.run_coroutine_threadsafe(self._send(message), loop)
        except Exception:
            pass

    @property
    def count(self) -> int:
        return len(self._clients)


manager = ConnectionManager()
