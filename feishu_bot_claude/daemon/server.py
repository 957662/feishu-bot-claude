"""Asyncio Unix-socket server. One Request → many ResponseEvents → DoneEvent → close."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from feishu_bot_claude.config.binding import BindingStore
from feishu_bot_claude.daemon.dispatcher import Dispatcher
from feishu_bot_claude.daemon.handlers import (
    handle_bind,
    handle_config,
    handle_list,
    handle_ping,
    handle_shell,
    handle_start,
    handle_status,
    handle_stop,
    handle_unbind,
)
from feishu_bot_claude.proto import DoneEvent, Request, ResultEvent

logger = logging.getLogger(__name__)


def _build_dispatcher(store: BindingStore) -> Dispatcher:
    d = Dispatcher()
    d.register("ping", handle_ping)
    d.register("status", handle_status)

    async def _list_with_store(args):
        async for ev in handle_list(args, store=store):
            yield ev
    d.register("list", _list_with_store)

    d.register("bind", handle_bind)
    d.register("unbind", handle_unbind)
    d.register("start", handle_start)
    d.register("stop", handle_stop)
    d.register("config", handle_config)
    d.register("shell", handle_shell)
    return d


async def _handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    dispatcher: Dispatcher,
) -> None:
    try:
        line = await reader.readline()
        if not line:
            return
        try:
            req = Request.from_json_line(line.decode().rstrip("\n"))
            req.validate()
        except (json.JSONDecodeError, ValueError) as e:
            await _write_event(writer, ResultEvent(ok=False, data=None, error=f"bad request: {e}"))
            await _write_event(writer, DoneEvent())
            return

        try:
            handler = dispatcher.lookup(req.op)
        except KeyError as e:
            await _write_event(writer, ResultEvent(ok=False, data=None, error=str(e)))
            await _write_event(writer, DoneEvent())
            return

        async for event in handler(req.args):
            await _write_event(writer, event)
    except Exception as e:  # noqa: BLE001
        logger.exception("client handler crashed")
        try:
            await _write_event(writer, ResultEvent(ok=False, data=None, error=f"server crash: {e}"))
            await _write_event(writer, DoneEvent())
        except Exception:
            pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def _write_event(writer: asyncio.StreamWriter, event) -> None:
    writer.write((event.to_json_line() + "\n").encode())
    await writer.drain()


async def serve(socket_path: Path, bindings_path: Path) -> asyncio.AbstractServer:
    """Start the daemon server bound to a Unix socket. Returns the running server."""
    socket_path = Path(socket_path)
    if socket_path.exists():
        socket_path.unlink()
    socket_path.parent.mkdir(parents=True, exist_ok=True)

    store = BindingStore(bindings_path)
    dispatcher = _build_dispatcher(store)

    async def _on_client(reader, writer):
        await _handle_client(reader, writer, dispatcher)

    server = await asyncio.start_unix_server(_on_client, path=str(socket_path))
    os.chmod(socket_path, 0o600)
    logger.info("daemon listening on %s", socket_path)
    return server
