"""
EventBus — central event dispatch for MeetingMind.

Bridges synchronous pipeline threads to async WebSocket clients.
Pipeline stages emit typed event dicts; the EventBus fans them out to:
  1. WebSocket clients (real-time UI updates)
  2. Python logger (preserving existing logging behaviour)
  3. Registered sync callbacks (e.g. database persistence)
"""

import asyncio
import logging
import threading
import time
from typing import Any, Callable

logger = logging.getLogger("meetingmind.events")

# Type alias for event payloads.
Event = dict[str, Any]

# Sync callback: called on the emitting thread.
SyncCallback = Callable[[Event], None]

# Async callback: scheduled on the event loop.
AsyncCallback = Callable[[Event], Any]


class EventBus:
    """Thread-safe event dispatcher.

    Sync callers (pipeline stages running on background threads) call
    ``emit(event)`` which:
      - Invokes all registered sync callbacks on the calling thread.
      - Schedules all registered async callbacks on the asyncio event loop
        using ``run_coroutine_threadsafe``.
      - Logs the event at DEBUG level.
    """

    def __init__(self) -> None:
        self._sync_callbacks: list[SyncCallback] = []
        self._async_callbacks: list[AsyncCallback] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Register the asyncio event loop for async dispatch."""
        self._loop = loop

    def subscribe_sync(self, callback: SyncCallback) -> None:
        """Register a synchronous callback (runs on emitter thread)."""
        with self._lock:
            self._sync_callbacks.append(callback)

    def subscribe_async(self, callback: AsyncCallback) -> None:
        """Register an async callback (scheduled on the event loop)."""
        with self._lock:
            self._async_callbacks.append(callback)

    def unsubscribe_sync(self, callback: SyncCallback) -> None:
        with self._lock:
            self._sync_callbacks = [
                cb for cb in self._sync_callbacks if cb is not callback
            ]

    def unsubscribe_async(self, callback: AsyncCallback) -> None:
        with self._lock:
            self._async_callbacks = [
                cb for cb in self._async_callbacks if cb is not callback
            ]

    def emit(self, event: Event) -> None:
        """Emit an event to all subscribers. Thread-safe.

        Called from any thread (typically pipeline background threads).
        Sync callbacks execute immediately; async callbacks are scheduled
        on the event loop without blocking.
        """
        # Ensure every event has a timestamp.
        if "timestamp" not in event:
            event["timestamp"] = time.time()

        logger.debug("Event: %s", event.get("type", "unknown"))

        # Sync callbacks — run on calling thread.
        with self._lock:
            sync_cbs = list(self._sync_callbacks)
        for cb in sync_cbs:
            try:
                cb(event)
            except Exception:
                logger.exception("Sync callback error for event %s", event.get("type"))

        # Async callbacks — schedule on event loop.
        loop = self._loop
        if loop is None or loop.is_closed():
            return

        with self._lock:
            async_cbs = list(self._async_callbacks)
        for cb in async_cbs:
            try:
                asyncio.run_coroutine_threadsafe(cb(event), loop)
            except Exception:
                logger.exception("Failed to schedule async callback for %s", event.get("type"))
