"""
WebSocket fan-out for the live activity stream.

Clients may subscribe to a single lab or to everything. Sends are best-effort:
a dead socket is dropped rather than retried, because the source of truth is
the database and a reconnecting client refetches.
"""
from typing import Any, Optional

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        # websocket -> lab_id filter (None = all labs)
        self._clients: dict[WebSocket, Optional[int]] = {}

    async def connect(self, ws: WebSocket, lab_id: Optional[int] = None) -> None:
        await ws.accept()
        self._clients[ws] = lab_id

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.pop(ws, None)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws, lab_filter in list(self._clients.items()):
            if lab_filter is not None and payload.get("lab_id") != lab_filter:
                continue
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def count(self) -> int:
        return len(self._clients)


manager = ConnectionManager()
