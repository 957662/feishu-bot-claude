"""CLI entry: socket client + Click commands + terminal rendering."""

from __future__ import annotations

import json

from feishu_bot_claude.proto import (
    DoneEvent,
    LogEvent,
    ProgressEvent,
    QRCodeEvent,
    ResponseEvent,
    ResultEvent,
)


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
