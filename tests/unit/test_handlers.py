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


from datetime import datetime, timezone
from pathlib import Path

from feishu_bot_claude.config.binding import BindingConfig, BindingStore
from feishu_bot_claude.daemon.handlers import handle_list


def _example_config(name="foo-bot", project_dir="/abs/foo") -> BindingConfig:
    return BindingConfig(
        name=name,
        project_dir=project_dir,
        tmux_session=f"claude-{name}",
        feishu_app_id=f"cli_{name}",
        secret_ref=f"feishu-bot-claude.{name}.app_secret",
        created_at=datetime(2026, 5, 26, 18, 50, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_list_returns_all_bindings(tmp_path):
    store = BindingStore(tmp_path / "bindings.toml")
    store.add(_example_config(name="foo-bot", project_dir="/abs/foo"))
    store.add(_example_config(name="bar-bot", project_dir="/abs/bar"))

    events = []
    async for ev in handle_list(args={}, store=store):
        events.append(ev)

    assert len(events) == 2  # ResultEvent + DoneEvent
    result = events[0]
    assert result.ok is True
    assert {b["name"] for b in result.data["bindings"]} == {"foo-bot", "bar-bot"}
    assert events[-1] == DoneEvent()


@pytest.mark.asyncio
async def test_list_empty_store(tmp_path):
    store = BindingStore(tmp_path / "bindings.toml")
    events = []
    async for ev in handle_list(args={}, store=store):
        events.append(ev)
    assert events[0].data == {"bindings": []}
