"""Tests for FakeLarkCli — records send/consume calls, replays canned events."""

import pytest

from feishu_bot_claude.daemon.feishu import FakeLarkCli, LarkCli


@pytest.mark.asyncio
async def test_fake_send_text_records():
    lark: LarkCli = FakeLarkCli()
    msg_id = await lark.send_text(chat_id="oc_xxx", text="hello", idempotency_key="k1")
    assert msg_id.startswith("om_fake_")
    assert lark.send_calls[-1] == {
        "kind": "text",
        "chat_id": "oc_xxx",
        "text": "hello",
        "idempotency_key": "k1",
    }


@pytest.mark.asyncio
async def test_fake_send_card_records():
    lark = FakeLarkCli()
    card = {"elements": [{"tag": "markdown", "content": "hi"}]}
    msg_id = await lark.send_card(chat_id="oc_xxx", card=card, idempotency_key="k2")
    assert msg_id.startswith("om_fake_")
    assert lark.send_calls[-1] == {
        "kind": "card",
        "chat_id": "oc_xxx",
        "card": card,
        "idempotency_key": "k2",
    }


@pytest.mark.asyncio
async def test_fake_update_card_records():
    lark = FakeLarkCli()
    card = {"elements": []}
    await lark.update_card(message_id="om_fake_1", card=card)
    assert lark.send_calls[-1] == {
        "kind": "update",
        "message_id": "om_fake_1",
        "card": card,
    }


@pytest.mark.asyncio
async def test_fake_consume_yields_queued_events():
    lark = FakeLarkCli()
    lark.enqueue_event({"type": "im.message.receive_v1", "event": {"message": {"content": '{"text":"hi"}'}}})
    lark.enqueue_event({"type": "im.message.receive_v1", "event": {"message": {"content": '{"text":"again"}'}}})

    received = []
    async for evt in lark.consume_events(event_key="im.message.receive_v1", max_events=2):
        received.append(evt)

    assert len(received) == 2
    assert received[0]["event"]["message"]["content"] == '{"text":"hi"}'


@pytest.mark.asyncio
async def test_fake_consume_obeys_max_events():
    lark = FakeLarkCli()
    for i in range(5):
        lark.enqueue_event({"event": {"i": i}})

    received = []
    async for evt in lark.consume_events(event_key="im.message.receive_v1", max_events=3):
        received.append(evt)
    assert len(received) == 3
