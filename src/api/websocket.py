"""
WebSocket connection manager for MeetingMind.

Maintains a set of connected WebSocket clients and broadcasts
events from the EventBus to all of them.
"""

import json
import logging
import threading

from fastapi import WebSocket

logger = logging.getLogger("meetingmind.websocket")


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts events."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = threading.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        with self._lock:
            self._connections.append(websocket)
        logger.info("WebSocket client connected (%d total)", len(self._connections))

    def add(self, websocket: WebSocket) -> None:
        """Register an already-accepted WebSocket connection."""
        with self._lock:
            self._connections.append(websocket)
        logger.info("WebSocket client connected (%d total)", len(self._connections))

    def disconnect(self, websocket: WebSocket) -> None:
        with self._lock:
            self._connections = [ws for ws in self._connections if ws is not websocket]
        logger.info("WebSocket client disconnected (%d remaining)", len(self._connections))

    async def broadcast(self, event: dict) -> None:
        """Send an event to all connected clients.

        Silently removes clients that have disconnected.
        """
        with self._lock:
            snapshot = list(self._connections)

        if not snapshot:
            return

        data = json.dumps(event)
        disconnected: list[WebSocket] = []

        for ws in snapshot:
            try:
                await ws.send_text(data)
            except Exception:
                disconnected.append(ws)

        if disconnected:
            with self._lock:
                self._connections = [ws for ws in self._connections if ws not in disconnected]
