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


from datetime import datetime, timezone

from feishu_bot_claude.config.binding import BindingConfig
from feishu_bot_claude.config.keychain import KeychainStore
from feishu_bot_claude.daemon.auth import bot_new
from feishu_bot_claude.daemon.menu import push_menu_with_fallback
from feishu_bot_claude.menu_template import build_menu_json
from feishu_bot_claude.proto import LogEvent, ProgressEvent, QRCodeEvent


def _extract_app_id_from_larkcli(profile_name: str) -> str:
    import os
    import json
    from pathlib import Path
    candidates = [
        Path.home() / ".lark-cli" / "profiles" / profile_name / "config.json",
        Path.home() / ".config" / "lark-cli" / "profiles" / profile_name / "config.json",
        Path.home() / ".lark-cli" / "profiles" / profile_name,
        Path.home() / ".config" / "lark-cli" / "profiles" / profile_name,
    ]
    for p in candidates:
        if p.is_file():
            try:
                data = json.loads(p.read_text())
                for key in ("app_id", "AppId", "appId"):
                    if key in data:
                        return data[key]
            except Exception:
                pass
        elif p.is_dir():
            for f in p.glob("*.json"):
                try:
                    data = json.loads(f.read_text())
                    for key in ("app_id", "AppId", "appId"):
                        if key in data:
                            return data[key]
                except Exception:
                    pass
    return f"larkcli-profile:{profile_name}"


async def handle_bind_with_orchestrator(
    args: dict,
    store: BindingStore,
    keychain: KeychainStore,
    auth_runner_factory,
    menu_pusher,
    data_dir,
) -> AsyncIterator[ResponseEvent]:
    name = args.get("name", "")
    cwd = args.get("cwd", "")
    if not name or not cwd:
        yield ResultEvent(ok=False, data=None, error="bind requires name and cwd")
        yield DoneEvent()
        return

    if store.find_by_cwd(cwd) is not None:
        yield ResultEvent(ok=False, data=None, error=f"cwd already bound: {cwd}")
        yield DoneEvent()
        return
    if store.find_by_name(name) is not None:
        yield ResultEvent(ok=False, data=None, error=f"name already exists: {name}")
        yield DoneEvent()
        return

    streamed: list = []

    async def _capture(event: dict) -> None:
        streamed.append(event)

    yield LogEvent(level="info", msg="Starting Feishu OAuth flow (扫码新建 App)...")
    try:
        creds = await bot_new(runner=auth_runner_factory(name), on_event=_capture)
    except RuntimeError as e:
        yield ResultEvent(ok=False, data=None, error=f"OAuth failed: {e}")
        yield DoneEvent()
        return

    for ev in streamed:
        if ev["type"] == "qrcode":
            yield QRCodeEvent(ascii=ev["ascii"], url=ev.get("url", ""))
        elif ev["type"] == "log":
            yield LogEvent(level=ev.get("level", "info"), msg=ev["msg"])
        elif ev["type"] == "progress":
            yield ProgressEvent(value=ev.get("value", 0.0), msg=ev.get("msg", ""))

    # Extract app_id from lark-cli profile config files (lark-cli manages creds internally)
    feishu_app_id = creds.app_id or _extract_app_id_from_larkcli(name)
    yield LogEvent(level="info", msg=f"App created: {feishu_app_id}")

    secret_ref = f"feishu-bot-claude.{name}.app_secret"
    # lark-cli manages the real secret internally; store empty string to satisfy data model
    keychain.put(secret_ref, creds.app_secret)

    from pathlib import Path
    binding = BindingConfig(
        name=name,
        project_dir=cwd,
        tmux_session=f"claude-{name}",
        feishu_app_id=feishu_app_id,
        secret_ref=secret_ref,
        created_at=datetime.now(timezone.utc),
    )
    store.add(binding)

    if menu_pusher is not None:
        menu_json = build_menu_json()
        menu_result = await push_menu_with_fallback(
            lark_menu=menu_pusher,
            app_id=feishu_app_id,
            menu_json=menu_json,
            fallback_dir=Path(data_dir) / "menus",
            binding_name=name,
        )
        if menu_result.method == "api":
            yield LogEvent(level="info", msg="Menu pushed via lark-cli API.")
        else:
            yield LogEvent(level="warn", msg=f"Menu API unsupported; JSON written to {menu_result.fallback_path}.")

    yield ResultEvent(
        ok=True,
        data={"name": name, "app_id": feishu_app_id, "next": "/bot-start"},
        error=None,
    )
    yield DoneEvent()


async def handle_unbind_with_orchestrator(
    args: dict,
    store: BindingStore,
    keychain: KeychainStore,
) -> AsyncIterator[ResponseEvent]:
    name = args.get("name", "")
    binding = store.find_by_name(name)
    if binding is None:
        yield ResultEvent(ok=False, data=None, error=f"no binding named {name!r}")
        yield DoneEvent()
        return
    store.remove(name)
    keychain.delete(binding.secret_ref)
    yield ResultEvent(ok=True, data={"removed": name}, error=None)
    yield DoneEvent()
