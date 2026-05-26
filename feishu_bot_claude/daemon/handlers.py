"""Daemon op handlers — async generators yielding ResponseEvents."""

from __future__ import annotations

from typing import AsyncIterator

from feishu_bot_claude.proto import DoneEvent, ResponseEvent, ResultEvent


async def handle_ping(args: dict) -> AsyncIterator[ResponseEvent]:
    """Liveness check. Yields a single ok result and done."""
    yield ResultEvent(ok=True, data={"pong": True}, error=None)
    yield DoneEvent()
