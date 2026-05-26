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


import time

import feishu_bot_claude

_DAEMON_START_TIME = time.time()


async def _not_implemented(op: str) -> AsyncIterator[ResponseEvent]:
    yield ResultEvent(ok=False, data=None, error=f"{op}: not yet implemented (later phase)")
    yield DoneEvent()


async def handle_bind(args: dict) -> AsyncIterator[ResponseEvent]:
    async for ev in _not_implemented("bind"):
        yield ev


async def handle_unbind(args: dict) -> AsyncIterator[ResponseEvent]:
    async for ev in _not_implemented("unbind"):
        yield ev


async def handle_start(args: dict) -> AsyncIterator[ResponseEvent]:
    async for ev in _not_implemented("start"):
        yield ev


async def handle_stop(args: dict) -> AsyncIterator[ResponseEvent]:
    async for ev in _not_implemented("stop"):
        yield ev


async def handle_config(args: dict) -> AsyncIterator[ResponseEvent]:
    async for ev in _not_implemented("config"):
        yield ev


async def handle_shell(args: dict) -> AsyncIterator[ResponseEvent]:
    async for ev in _not_implemented("shell"):
        yield ev


async def handle_status(args: dict) -> AsyncIterator[ResponseEvent]:
    yield ResultEvent(
        ok=True,
        data={
            "version": feishu_bot_claude.__version__,
            "uptime_seconds": int(time.time() - _DAEMON_START_TIME),
        },
        error=None,
    )
    yield DoneEvent()


from pathlib import Path

from feishu_bot_claude.daemon.orchestrator import Orchestrator


async def handle_start_with_orchestrator(args: dict, orchestrator: Orchestrator) -> AsyncIterator[ResponseEvent]:
    cwd = args.get("cwd", "")
    jsonl_path_str = args.get("jsonl_path")
    jsonl_path = Path(jsonl_path_str) if jsonl_path_str else None
    try:
        running = await orchestrator.start_binding(cwd=cwd, jsonl_path=jsonl_path)
        yield ResultEvent(
            ok=True,
            data={"name": running.config.name, "tmux_session": running.config.tmux_session},
            error=None,
        )
    except KeyError as e:
        yield ResultEvent(ok=False, data=None, error=str(e))
    except RuntimeError as e:
        yield ResultEvent(ok=False, data=None, error=str(e))
    yield DoneEvent()


async def handle_stop_with_orchestrator(args: dict, orchestrator: Orchestrator) -> AsyncIterator[ResponseEvent]:
    cwd = args.get("cwd", "")
    try:
        await orchestrator.stop_binding(cwd=cwd)
        yield ResultEvent(ok=True, data={"stopped": True}, error=None)
    except KeyError as e:
        yield ResultEvent(ok=False, data=None, error=str(e))
    yield DoneEvent()
