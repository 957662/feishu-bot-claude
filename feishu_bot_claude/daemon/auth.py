"""OAuth bot-new flow wrapper: parses lark-cli output, emits qrcode/progress events."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import AsyncIterator, Awaitable, Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BotCreationResult:
    app_id: str
    app_secret: str
    tenant_key: str | None = None


_QR_DELIMITER = "===QR==="
_URL_PREFIX = "URL:"
_CREDS_PATTERN = re.compile(r'^\s*\{.*"app_id"\s*:\s*"([^"]+)".*"app_secret"\s*:\s*"([^"]+)"')


async def bot_new(
    runner: AsyncIterator[str],
    on_event: Callable[[dict], Awaitable[None] | None],
) -> BotCreationResult:
    """Drive the bot-new flow, parsing QR + URL + creds from a stream of output lines.

    `runner` is an async iterator yielding output lines. `on_event` is called
    with each `{type: "qrcode"|"progress"|"log", ...}` event for streaming back
    to the CLI via the IPC protocol.

    Returns the parsed credentials. Raises if the flow ends without creds.
    """
    in_qr = False
    qr_lines: list[str] = []
    pending_qr_ascii: str | None = None  # QR ascii waiting for its URL line

    async def _emit(event: dict) -> None:
        result = on_event(event)
        if asyncio.iscoroutine(result):
            await result

    async def _flush_pending_qr(url: str = "") -> None:
        nonlocal pending_qr_ascii
        if pending_qr_ascii is not None:
            await _emit({"type": "qrcode", "ascii": pending_qr_ascii, "url": url})
            pending_qr_ascii = None

    async for line in runner:
        line = line.rstrip("\n")

        if line.strip() == _QR_DELIMITER:
            if in_qr:
                # Closing delimiter: stash the ascii art, wait for URL line
                pending_qr_ascii = "\n".join(qr_lines)
                in_qr = False
                qr_lines = []
            else:
                # Opening delimiter: flush any previous pending QR first
                await _flush_pending_qr()
                in_qr = True
                qr_lines = []
            continue

        if in_qr:
            qr_lines.append(line)
            continue

        if line.startswith(_URL_PREFIX):
            url = line[len(_URL_PREFIX):].strip()
            await _flush_pending_qr(url)
            continue

        m = _CREDS_PATTERN.match(line)
        if m:
            payload = json.loads(line)
            return BotCreationResult(
                app_id=payload["app_id"],
                app_secret=payload["app_secret"],
                tenant_key=payload.get("tenant_key"),
            )

        if line.strip():
            await _emit({"type": "log", "level": "info", "msg": line})

    raise RuntimeError("auth flow failed: subprocess ended without credentials")
