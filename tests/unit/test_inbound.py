"""Tests for InboundPipeline — Feishu events → tmux send-keys."""

import json

import pytest

from feishu_bot_claude.daemon.feishu import FakeLarkCli
from feishu_bot_claude.daemon.inbound import InboundPipeline
from feishu_bot_claude.daemon.tmux import FakeTmux


def _text_event(text: str, sender_id: str = "ou_user") -> dict:
    return {
        "type": "im.message.receive_v1",
        "event": {
            "sender": {"sender_id": {"open_id": sender_id}},
            "message": {
                "message_type": "text",
                "content": json.dumps({"text": text}),
            },
        },
    }


def _menu_event(event_key: str, sender_id: str = "ou_user") -> dict:
    return {
        "type": "application.bot.menu_v6",
        "event": {
            "operator": {"operator_id": {"open_id": sender_id}},
            "event_key": event_key,
        },
    }


@pytest.mark.asyncio
async def test_inbound_routes_text_to_tmux():
    tmux = FakeTmux()
    tmux.set_session("claude-foo", exists=True)
    lark = FakeLarkCli()
    lark.enqueue_event(_text_event("hello claude"))

    pipeline = InboundPipeline(
        tmux_session="claude-foo",
        tmux=tmux,
        lark=lark,
    )
    await pipeline.process_until_idle(max_events=1)

    send_keys_calls = [c for c in tmux.calls if c[0] == "send_keys"]
    assert len(send_keys_calls) == 1
    assert send_keys_calls[0][1]["keys"] == "hello claude\n"


@pytest.mark.asyncio
async def test_inbound_routes_slash_command_to_tmux():
    tmux = FakeTmux()
    tmux.set_session("claude-foo", exists=True)
    lark = FakeLarkCli()
    lark.enqueue_event(_text_event("/compact"))

    pipeline = InboundPipeline(
        tmux_session="claude-foo", tmux=tmux, lark=lark,
    )
    await pipeline.process_until_idle(max_events=1)

    send_keys_calls = [c for c in tmux.calls if c[0] == "send_keys"]
    assert send_keys_calls[0][1]["keys"] == "/compact\n"


@pytest.mark.asyncio
async def test_inbound_routes_menu_button_to_command():
    tmux = FakeTmux()
    tmux.set_session("claude-foo", exists=True)
    lark = FakeLarkCli()
    lark.enqueue_event(_menu_event("cmd_clear"))

    pipeline = InboundPipeline(
        tmux_session="claude-foo", tmux=tmux, lark=lark,
        menu_command_map={"cmd_clear": "/clear", "cmd_compact": "/compact"},
    )
    await pipeline.process_until_idle(max_events=1)

    send_keys_calls = [c for c in tmux.calls if c[0] == "send_keys"]
    assert send_keys_calls[0][1]["keys"] == "/clear\n"


@pytest.mark.asyncio
async def test_inbound_unknown_menu_key_logs_and_skips():
    tmux = FakeTmux()
    tmux.set_session("claude-foo", exists=True)
    lark = FakeLarkCli()
    lark.enqueue_event(_menu_event("totally_unknown_key"))

    pipeline = InboundPipeline(
        tmux_session="claude-foo", tmux=tmux, lark=lark,
        menu_command_map={"cmd_clear": "/clear"},
    )
    await pipeline.process_until_idle(max_events=1)

    send_keys_calls = [c for c in tmux.calls if c[0] == "send_keys"]
    assert send_keys_calls == []


@pytest.mark.asyncio
async def test_inbound_whitelist_drops_other_senders():
    tmux = FakeTmux()
    tmux.set_session("claude-foo", exists=True)
    lark = FakeLarkCli()
    lark.enqueue_event(_text_event("hi", sender_id="ou_attacker"))

    pipeline = InboundPipeline(
        tmux_session="claude-foo", tmux=tmux, lark=lark,
        allow_users={"ou_owner"},
    )
    await pipeline.process_until_idle(max_events=1)

    send_keys_calls = [c for c in tmux.calls if c[0] == "send_keys"]
    assert send_keys_calls == []


@pytest.mark.asyncio
async def test_inbound_truncates_long_message():
    tmux = FakeTmux()
    tmux.set_session("claude-foo", exists=True)
    lark = FakeLarkCli()
    lark.enqueue_event(_text_event("x" * 20_000))

    pipeline = InboundPipeline(
        tmux_session="claude-foo", tmux=tmux, lark=lark,
        max_message_length=100,
    )
    await pipeline.process_until_idle(max_events=1)

    send_keys_calls = [c for c in tmux.calls if c[0] == "send_keys"]
    assert send_keys_calls
    keys = send_keys_calls[0][1]["keys"]
    assert len(keys) <= 200
