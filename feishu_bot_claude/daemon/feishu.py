"""lark-cli subprocess wrapper: real + fake implementations.

Real implementation spawns `lark-cli` subprocesses for each operation.
Fake records calls and replays canned NDJSON events for tests.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import AsyncIterator


class LarkCli(ABC):
    """Async wrapper around the `lark-cli` binary."""

    @abstractmethod
    async def send_text(self, chat_id: str, text: str, idempotency_key: str | None = None) -> str:
        """Send a plain text message. Returns the message_id (om_xxx)."""

    @abstractmethod
    async def send_card(self, chat_id: str, card: dict, idempotency_key: str | None = None) -> str:
        """Send an interactive card. Returns the message_id."""

    @abstractmethod
    async def update_card(self, message_id: str, card: dict) -> None:
        """Update the content of a previously-sent card by message_id."""

    @abstractmethod
    def consume_events(self, event_key: str, max_events: int = 0) -> AsyncIterator[dict]:
        """Subscribe to a Feishu event key, yielding event dicts as they arrive.

        max_events=0 means unlimited.
        """


class FakeLarkCli(LarkCli):
    """In-memory fake — records send calls, replays queued consume events."""

    def __init__(self) -> None:
        self.send_calls: list[dict] = []
        self._consume_queue: list[dict] = []
        self._counter = 0

    def _next_message_id(self) -> str:
        self._counter += 1
        return f"om_fake_{self._counter}"

    def enqueue_event(self, event: dict) -> None:
        """Test helper: add an event for the next consume() call to yield."""
        self._consume_queue.append(event)

    async def send_text(self, chat_id: str, text: str, idempotency_key: str | None = None) -> str:
        self.send_calls.append({
            "kind": "text",
            "chat_id": chat_id,
            "text": text,
            "idempotency_key": idempotency_key,
        })
        return self._next_message_id()

    async def send_card(self, chat_id: str, card: dict, idempotency_key: str | None = None) -> str:
        self.send_calls.append({
            "kind": "card",
            "chat_id": chat_id,
            "card": card,
            "idempotency_key": idempotency_key,
        })
        return self._next_message_id()

    async def update_card(self, message_id: str, card: dict) -> None:
        self.send_calls.append({
            "kind": "update",
            "message_id": message_id,
            "card": card,
        })

    async def consume_events(self, event_key: str, max_events: int = 0) -> AsyncIterator[dict]:
        emitted = 0
        while True:
            if not self._consume_queue:
                break
            yield self._consume_queue.pop(0)
            emitted += 1
            if max_events > 0 and emitted >= max_events:
                break
