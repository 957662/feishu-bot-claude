"""CLI entry: socket client + Click commands + terminal rendering."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import AsyncIterator

from feishu_bot_claude.proto import (
    DoneEvent,
    LogEvent,
    ProgressEvent,
    QRCodeEvent,
    ResponseEvent,
    ResultEvent,
    parse_response_line,
    Request,
)


async def run_op(
    socket_path: Path,
    op: str,
    args: dict,
    request_id: str = "",
) -> AsyncIterator[ResponseEvent]:
    """Open the daemon socket, send one Request, yield ResponseEvents until done.

    Yields events as they stream in (real-time UI feedback).
    Raises ConnectionRefusedError if the daemon is not running.
    """
    reader, writer = await asyncio.open_unix_connection(str(socket_path))
    try:
        req = Request(op=op, args=args, request_id=request_id)
        writer.write((req.to_json_line() + "\n").encode())
        await writer.drain()

        while True:
            line = await reader.readline()
            if not line:
                break
            event = parse_response_line(line.decode().rstrip("\n"))
            yield event
            if isinstance(event, DoneEvent):
                break
    finally:
        writer.close()
        await writer.wait_closed()


def render_event(event: ResponseEvent) -> str:
    """Format one ResponseEvent into a single terminal-ready string.

    Returns "" for DoneEvent (caller does nothing with it).
    """
    if isinstance(event, LogEvent):
        if event.level == "error":
            return f"ERROR: {event.msg}"
        if event.level == "warn":
            return f"WARN: {event.msg}"
        return event.msg
    if isinstance(event, QRCodeEvent):
        return f"{event.ascii}\n\nURL: {event.url}"
    if isinstance(event, ProgressEvent):
        pct = int(event.value * 100)
        return f"[{pct}%] {event.msg}"
    if isinstance(event, ResultEvent):
        if event.ok:
            payload = json.dumps(event.data, ensure_ascii=False, indent=2) if event.data else ""
            return f"OK\n{payload}" if payload else "OK"
        return f"FAILED: {event.error}"
    if isinstance(event, DoneEvent):
        return ""
    return repr(event)
