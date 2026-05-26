"""lark-cli subprocess wrapper: real + fake implementations.

Real implementation spawns `lark-cli` subprocesses for each operation.
Fake records calls and replays canned NDJSON events for tests.
"""

from __future__ import annotations

import asyncio
import json
import os
from abc import ABC, abstractmethod
from typing import AsyncIterator


class LarkCli(ABC):
    """Async wrapper around the `lark-cli` binary."""

    @abstractmethod
    async def send_text(self, chat_id: str, text: str, idempotency_key: str | None = None) -> str:
        """Send a plain text message. Returns the message_id (om_xxx)."""

    @abstractmethod
    async def send_card(self, chat_id: str, card: dict, idempotency_key: str | None = None) -> str:
        """Send an interactive card. Returns the message_id."""

    @abstractmethod
    async def update_card(self, message_id: str, card: dict) -> None:
        """Update the content of a previously-sent card by message_id."""

    @abstractmethod
    def consume_events(self, event_key: str, max_events: int = 0) -> AsyncIterator[dict]:
        """Subscribe to a Feishu event key, yielding event dicts as they arrive.

        max_events=0 means unlimited.
        """

    @abstractmethod
    def auth_bot_new_stream(self) -> AsyncIterator[str]:
        """Spawn `lark-cli auth bot-new` and stream its stdout line-by-line."""

    @abstractmethod
    async def push_menu(self, app_id: str, menu_json: dict) -> None:
        """Push a menu config to the Feishu open platform for `app_id`."""


class FakeLarkCli(LarkCli):
    """In-memory fake — records send calls, replays queued consume events."""

    def __init__(self) -> None:
        self.send_calls: list[dict] = []
        self._consume_queue: list[dict] = []
        self._counter = 0
        self._auth_lines: list[str] = []
        self._auth_should_fail = False
        self._menu_pushes: list[dict] = []
        self._menu_should_fail = False

    def _next_message_id(self) -> str:
        self._counter += 1
        return f"om_fake_{self._counter}"

    def enqueue_event(self, event: dict) -> None:
        """Test helper: add an event for the next consume() call to yield."""
        self._consume_queue.append(event)

    def set_auth_lines(self, lines: list[str]) -> None:
        """Test helper: lines to emit from auth_bot_new_stream."""
        self._auth_lines = list(lines)

    def fail_menu_push(self, fail: bool = True) -> None:
        self._menu_should_fail = fail

    async def send_text(self, chat_id: str, text: str, idempotency_key: str | None = None) -> str:
        self.send_calls.append({
            "kind": "text",
            "chat_id": chat_id,
            "text": text,
            "idempotency_key": idempotency_key,
        })
        return self._next_message_id()

    async def send_card(self, chat_id: str, card: dict, idempotency_key: str | None = None) -> str:
        self.send_calls.append({
            "kind": "card",
            "chat_id": chat_id,
            "card": card,
            "idempotency_key": idempotency_key,
        })
        return self._next_message_id()

    async def update_card(self, message_id: str, card: dict) -> None:
        self.send_calls.append({
            "kind": "update",
            "message_id": message_id,
            "card": card,
        })

    async def consume_events(self, event_key: str, max_events: int = 0) -> AsyncIterator[dict]:
        emitted = 0
        while True:
            if not self._consume_queue:
                break
            yield self._consume_queue.pop(0)
            emitted += 1
            if max_events > 0 and emitted >= max_events:
                break

    async def auth_bot_new_stream(self) -> AsyncIterator[str]:
        for line in self._auth_lines:
            await asyncio.sleep(0)
            yield line + "\n"

    async def push_menu(self, app_id: str, menu_json: dict) -> None:
        if self._menu_should_fail:
            raise RuntimeError("fake menu API failure")
        self._menu_pushes.append({"app_id": app_id, "menu": menu_json})


class RealLarkCli(LarkCli):
    """Real backend — spawns `lark-cli` subprocesses for each operation.

    Authentication is expected to be set up externally before instantiating
    this (via `lark-cli auth login` or via env vars). Each `send`/`consume`
    runs a fresh subprocess.
    """

    def __init__(self, binary: str = "lark-cli", as_bot: bool = True, extra_env: dict[str, str] | None = None) -> None:
        self._binary = binary
        self._as_bot = as_bot
        self._extra_env = dict(extra_env or {})

    async def _run_raw(self, args: list[str], timeout: float = 30.0) -> tuple[str, int]:
        """Run `lark-cli <args>`. Return (stdout, returncode)."""
        env = os.environ.copy()
        env.update(self._extra_env)
        proc = await asyncio.create_subprocess_exec(
            self._binary, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise
        return stdout.decode(), proc.returncode

    def _common_args(self) -> list[str]:
        return ["--as", "bot"] if self._as_bot else []

    async def send_text(self, chat_id: str, text: str, idempotency_key: str | None = None) -> str:
        args = [
            "im", "+messages-send",
            *self._common_args(),
            "--chat-id", chat_id,
            "--type", "text",
            "--text", text,
        ]
        if idempotency_key:
            args += ["--idempotency-key", idempotency_key]
        out, code = await self._run_raw(args, timeout=30.0)
        if code != 0:
            raise RuntimeError(f"lark-cli im +messages-send failed (exit {code}): {out!r}")
        try:
            payload = json.loads(out.strip().splitlines()[-1])
            return payload["message_id"]
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            raise RuntimeError(f"could not extract message_id from lark-cli output: {out!r}") from e

    async def send_card(self, chat_id: str, card: dict, idempotency_key: str | None = None) -> str:
        args = [
            "im", "+messages-send",
            *self._common_args(),
            "--chat-id", chat_id,
            "--type", "interactive",
            "--card", json.dumps(card, ensure_ascii=False),
        ]
        if idempotency_key:
            args += ["--idempotency-key", idempotency_key]
        out, code = await self._run_raw(args, timeout=30.0)
        if code != 0:
            raise RuntimeError(f"lark-cli send_card failed (exit {code}): {out!r}")
        try:
            payload = json.loads(out.strip().splitlines()[-1])
            return payload["message_id"]
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            raise RuntimeError(f"could not extract message_id: {out!r}") from e

    async def update_card(self, message_id: str, card: dict) -> None:
        args = [
            "im", "messages", "patch",
            *self._common_args(),
            "--message-id", message_id,
            "--card", json.dumps(card, ensure_ascii=False),
        ]
        out, code = await self._run_raw(args, timeout=30.0)
        if code != 0:
            raise RuntimeError(f"lark-cli update_card failed (exit {code}): {out!r}")

    async def consume_events(self, event_key: str, max_events: int = 0) -> AsyncIterator[dict]:
        args = [
            "event", "consume", event_key,
            *self._common_args(),
        ]
        if max_events > 0:
            args += ["--max-events", str(max_events)]

        env = os.environ.copy()
        env.update(self._extra_env)
        proc = await asyncio.create_subprocess_exec(
            self._binary, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                line_str = line.decode().rstrip("\n")
                if not line_str.strip():
                    continue
                try:
                    yield json.loads(line_str)
                except json.JSONDecodeError:
                    continue
        finally:
            if proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()

    async def auth_bot_new_stream(self) -> AsyncIterator[str]:
        proc = await asyncio.create_subprocess_exec(
            self._binary, "auth", "bot-new",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=os.environ.copy(),
        )
        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                yield line.decode("utf-8", errors="replace")
        finally:
            if proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=10.0)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()

    async def push_menu(self, app_id: str, menu_json: dict) -> None:
        """Push menu config via lark-cli. Subcommand may vary; raises on failure."""
        args = [
            "apps", "menu", "update",
            "--app-id", app_id,
            "--menu", json.dumps(menu_json, ensure_ascii=False),
        ]
        out, code = await self._run_raw(args, timeout=30.0)
        if code != 0:
            raise RuntimeError(f"lark-cli menu update failed (exit {code}): {out!r}")
