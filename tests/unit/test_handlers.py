"""Tests for daemon handlers (with mocked BindingStore)."""

import pytest

from feishu_bot_claude.daemon.handlers import handle_ping
from feishu_bot_claude.proto import DoneEvent, ResultEvent


@pytest.mark.asyncio
async def test_ping_emits_result_then_done():
    """ping yields a ResultEvent(ok=True, data={pong: True}) then DoneEvent."""
    events = []
    async for ev in handle_ping(args={}):
        events.append(ev)
    assert events == [
        ResultEvent(ok=True, data={"pong": True}, error=None),
        DoneEvent(),
    ]
