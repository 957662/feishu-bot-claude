"""Tests for auth.bot_new — drives lark-cli QR-scan, parses output, returns creds."""

import asyncio

import pytest

from feishu_bot_claude.daemon.auth import BotCreationResult, bot_new


async def _async_lines(lines: list[str]):
    """Helper: turn a list of lines into an async iterator yielding each with newline."""
    for line in lines:
        await asyncio.sleep(0)
        yield line + "\n"


@pytest.mark.asyncio
async def test_bot_new_parses_qr_then_success():
    """When subprocess emits a QR ASCII block then a credentials line, return parsed creds."""
    fake_output = [
        "[lark-cli] starting auth flow...",
        "===QR===",
        "█▀▀▀▀▀█ ▄ █▀▀▀▀▀█",
        "█ ███ █  ▀ █ ███ █",
        "===QR===",
        "URL: https://open.feishu.cn/app/cli_xxx/qr",
        "[lark-cli] waiting for scan...",
        '{"app_id":"cli_xxx123","app_secret":"sec_yyy456","tenant_key":"t"}',
    ]
    progress_events: list[dict] = []

    async def on_progress(event):
        progress_events.append(event)

    result = await bot_new(
        runner=_async_lines(fake_output),
        on_event=on_progress,
    )

    assert isinstance(result, BotCreationResult)
    assert result.app_id == "cli_xxx123"
    assert result.app_secret == "sec_yyy456"

    qr_events = [e for e in progress_events if e["type"] == "qrcode"]
    assert len(qr_events) == 1
    assert "█▀▀▀▀▀█" in qr_events[0]["ascii"]
    assert qr_events[0]["url"].startswith("https://open.feishu.cn")


@pytest.mark.asyncio
async def test_bot_new_no_creds_raises():
    """If lark-cli exits without emitting a creds line, raise."""
    with pytest.raises(RuntimeError, match="auth flow failed"):
        await bot_new(runner=_async_lines(["[lark-cli] error: timeout"]), on_event=lambda e: None)
