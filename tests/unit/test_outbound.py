"""Tests for OutboundPipeline — jsonl tail → card send/update."""

import asyncio
import json
from pathlib import Path

import pytest

from feishu_bot_claude.daemon.feishu import FakeLarkCli
from feishu_bot_claude.daemon.outbound import OutboundPipeline
from feishu_bot_claude.daemon.ratelimit import TokenBucket
from feishu_bot_claude.daemon.state import BindingRuntimeState


def _append_event(path: Path, event: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


@pytest.mark.asyncio
async def test_outbound_processes_existing_events_on_start(tmp_path):
    jsonl = tmp_path / "session.jsonl"
    _append_event(jsonl, {"role": "user", "uuid": "u1", "content": [{"type": "text", "text": "hi"}]})
    _append_event(jsonl, {"role": "assistant", "uuid": "a1", "content": [{"type": "text", "text": "hello"}]})

    lark = FakeLarkCli()
    state = BindingRuntimeState(binding_name="foo")
    pipeline = OutboundPipeline(
        jsonl_path=jsonl,
        chat_id="oc_xxx",
        project_name="foo",
        state=state,
        lark=lark,
        bucket=TokenBucket(rate_per_sec=100, capacity=10),
        render_style="rich",
    )
    await pipeline.process_backlog()
    card_sends = [c for c in lark.send_calls if c.get("kind") == "card"]
    assert len(card_sends) == 1
    assert state.jsonl_offset > 0


@pytest.mark.asyncio
async def test_outbound_updates_card_on_tool_use(tmp_path):
    jsonl = tmp_path / "session.jsonl"
    _append_event(jsonl, {"role": "user", "uuid": "u1", "content": [{"type": "text", "text": "read it"}]})
    _append_event(jsonl, {"role": "assistant", "uuid": "a1", "content": [
        {"type": "text", "text": "ok"},
        {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "/x"}},
    ]})
    _append_event(jsonl, {"role": "user", "uuid": "u2", "content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": "data"},
    ]})

    lark = FakeLarkCli()
    state = BindingRuntimeState(binding_name="foo")
    pipeline = OutboundPipeline(
        jsonl_path=jsonl, chat_id="oc_xxx", project_name="foo",
        state=state, lark=lark,
        bucket=TokenBucket(rate_per_sec=100, capacity=10),
        render_style="rich",
    )
    await pipeline.process_backlog()
    kinds = [c["kind"] for c in lark.send_calls]
    assert kinds.count("card") == 1
    assert kinds.count("update") >= 1


@pytest.mark.asyncio
async def test_outbound_new_user_event_creates_new_card(tmp_path):
    jsonl = tmp_path / "session.jsonl"
    _append_event(jsonl, {"role": "user", "uuid": "u1", "content": [{"type": "text", "text": "first"}]})
    _append_event(jsonl, {"role": "assistant", "uuid": "a1", "content": [{"type": "text", "text": "a"}]})
    _append_event(jsonl, {"role": "user", "uuid": "u2", "content": [{"type": "text", "text": "second"}]})
    _append_event(jsonl, {"role": "assistant", "uuid": "a2", "content": [{"type": "text", "text": "b"}]})

    lark = FakeLarkCli()
    state = BindingRuntimeState(binding_name="foo")
    pipeline = OutboundPipeline(
        jsonl_path=jsonl, chat_id="oc_xxx", project_name="foo",
        state=state, lark=lark,
        bucket=TokenBucket(rate_per_sec=100, capacity=10),
        render_style="rich",
    )
    await pipeline.process_backlog()
    card_sends = [c for c in lark.send_calls if c["kind"] == "card"]
    assert len(card_sends) == 2


@pytest.mark.asyncio
async def test_outbound_resume_from_offset(tmp_path):
    jsonl = tmp_path / "session.jsonl"
    _append_event(jsonl, {"role": "user", "uuid": "u1", "content": [{"type": "text", "text": "first"}]})
    _append_event(jsonl, {"role": "assistant", "uuid": "a1", "content": [{"type": "text", "text": "a"}]})

    lark = FakeLarkCli()
    state = BindingRuntimeState(binding_name="foo")
    state.jsonl_offset = jsonl.stat().st_size

    pipeline = OutboundPipeline(
        jsonl_path=jsonl, chat_id="oc_xxx", project_name="foo",
        state=state, lark=lark,
        bucket=TokenBucket(rate_per_sec=100, capacity=10),
        render_style="rich",
    )
    await pipeline.process_backlog()
    assert lark.send_calls == []

    _append_event(jsonl, {"role": "user", "uuid": "u2", "content": [{"type": "text", "text": "second"}]})
    _append_event(jsonl, {"role": "assistant", "uuid": "a2", "content": [{"type": "text", "text": "b"}]})

    await pipeline.process_backlog()
    card_sends = [c for c in lark.send_calls if c["kind"] == "card"]
    assert len(card_sends) == 1
