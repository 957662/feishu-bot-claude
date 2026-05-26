"""Daemon op handlers — async generators yielding ResponseEvents."""

from __future__ import annotations

from typing import AsyncIterator

from feishu_bot_claude.proto import DoneEvent, ResponseEvent, ResultEvent


async def handle_ping(args: dict) -> AsyncIterator[ResponseEvent]:
    """Liveness check. Yields a single ok result and done."""
    yield ResultEvent(ok=True, data={"pong": True}, error=None)
    yield DoneEvent()


from feishu_bot_claude.config.binding import BindingStore


def _binding_summary(b) -> dict:
    return {
        "name": b.name,
        "project_dir": b.project_dir,
        "tmux_session": b.tmux_session,
        "feishu_app_id": b.feishu_app_id,
        "render_style": b.render_style,
    }


async def handle_list(args: dict, store: BindingStore) -> AsyncIterator[ResponseEvent]:
    """Return all bindings as a list of summary dicts."""
    bindings = [_binding_summary(b) for b in store.all()]
    yield ResultEvent(ok=True, data={"bindings": bindings}, error=None)
    yield DoneEvent()
