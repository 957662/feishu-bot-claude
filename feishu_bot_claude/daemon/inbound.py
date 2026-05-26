"""Inbound pipeline: Feishu events → tmux send-keys (text/slash/menu)."""

from __future__ import annotations

import json
import logging

from feishu_bot_claude.daemon.feishu import LarkCli
from feishu_bot_claude.daemon.tmux import Tmux

logger = logging.getLogger(__name__)

# Standard confirmation event_key → tmux keystrokes (for /clear-style Y/N prompts).
# Orchestrator merges this into its menu_command_map by default.
DEFAULT_CONFIRM_MAP: dict[str, str] = {
    "confirm_yes": "y",
    "confirm_no": "n",
}


class InboundPipeline:
    """Drive `lark-cli event consume`, route each event to tmux or a handler."""

    def __init__(
        self,
        tmux_session: str,
        tmux: Tmux,
        lark: LarkCli,
        menu_command_map: dict[str, str] | None = None,
        allow_users: set[str] | None = None,
        max_message_length: int = 8000,
        event_key: str = "im.message.receive_v1",
    ) -> None:
        self._tmux_session = tmux_session
        self._tmux = tmux
        self._lark = lark
        self._menu_command_map = menu_command_map or {}
        self._allow_users = allow_users
        self._max_message_length = max_message_length
        self._event_key = event_key

    async def process_until_idle(self, max_events: int = 0) -> None:
        """Consume events until the fake queue drains or max_events hit."""
        count = 0
        async for event in self._lark.consume_events(self._event_key, max_events=max_events):
            await self._handle(event)
            count += 1
            if max_events and count >= max_events:
                break

    async def _handle(self, event: dict) -> None:
        evt_type = event.get("type", "")
        if evt_type == "im.message.receive_v1":
            await self._handle_message(event)
        elif evt_type == "application.bot.menu_v6":
            await self._handle_menu(event)
        else:
            logger.debug("ignoring event type: %s", evt_type)

    async def _handle_message(self, event: dict) -> None:
        msg = event.get("event", {}).get("message", {})
        sender = event.get("event", {}).get("sender", {}).get("sender_id", {}).get("open_id", "")
        if self._allow_users is not None and sender not in self._allow_users:
            logger.info("dropping message from non-whitelisted sender %s", sender)
            return
        if msg.get("message_type") != "text":
            logger.info("skipping non-text message type: %s", msg.get("message_type"))
            return
        content_json = msg.get("content", "{}")
        try:
            text = json.loads(content_json).get("text", "")
        except json.JSONDecodeError:
            logger.warning("malformed message content: %r", content_json[:80])
            return
        if not text:
            return
        if len(text) > self._max_message_length:
            text = text[: self._max_message_length] + "\n...[truncated]"
        self._tmux.send_keys(session=self._tmux_session, keys=text + "\n")

    async def _handle_menu(self, event: dict) -> None:
        ev = event.get("event", {})
        sender = ev.get("operator", {}).get("operator_id", {}).get("open_id", "")
        if self._allow_users is not None and sender not in self._allow_users:
            return
        event_key = ev.get("event_key", "")
        command = self._menu_command_map.get(event_key)
        if command is None:
            logger.info("unknown menu event_key: %s", event_key)
            return
        self._tmux.send_keys(session=self._tmux_session, keys=command + "\n")
