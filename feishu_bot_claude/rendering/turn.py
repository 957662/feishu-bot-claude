"""Group raw Claude jsonl events into Turns for rendering."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator


@dataclass(frozen=True)
class JsonlEvent:
    """One line from Claude's session jsonl."""

    role: str
    uuid: str
    content: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> JsonlEvent:
        return cls(
            role=d.get("role", ""),
            uuid=d.get("uuid", ""),
            content=d.get("content", []),
            raw=d,
        )

    @classmethod
    def load_file(cls, path: Path) -> Iterator[JsonlEvent]:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                yield cls.from_dict(json.loads(line))

    def text(self) -> str:
        return "".join(c.get("text", "") for c in self.content if c.get("type") == "text")

    def has_only_tool_results(self) -> bool:
        if not self.content:
            return False
        return all(c.get("type") == "tool_result" for c in self.content)


@dataclass
class Turn:
    """One conversation turn: a user message and the assistant response(s)."""

    user_event: JsonlEvent | None
    assistant_events: list[JsonlEvent] = field(default_factory=list)


def group_into_turns(events: Iterable[JsonlEvent]) -> list[Turn]:
    """Group an iterable of JsonlEvents into Turn list.

    A new Turn starts on a `user` event that contains at least one text part
    (i.e., a real user message, not just tool_result delivery).
    """
    turns: list[Turn] = []
    current: Turn | None = None

    for event in events:
        if event.role == "user" and not event.has_only_tool_results():
            current = Turn(user_event=event)
            turns.append(current)
        else:
            if current is None:
                current = Turn(user_event=None)
                turns.append(current)
            current.assistant_events.append(event)

    return turns


from feishu_bot_claude.rendering.card import build_card, build_header, build_markdown, build_note
from feishu_bot_claude.rendering.tools import render_tool_block


def render_turn_to_card(turn: Turn, project_name: str = "project", render_style: str = "rich") -> dict:
    """Render a Turn to a Feishu interactive card JSON."""
    elements: list[dict] = []
    for event in turn.assistant_events:
        for part in event.content:
            if part.get("type") == "text" and part.get("text"):
                elements.append(build_markdown(part["text"]))
            elif part.get("type") == "tool_use":
                tool_use = part
                tool_result = None
                for later in turn.assistant_events:
                    for p in later.content:
                        if p.get("type") == "tool_result" and p.get("tool_use_id") == tool_use.get("id"):
                            tool_result = p
                            break
                block = render_tool_block(tool_use, tool_result, render_style=render_style)
                if block is not None:
                    elements.append(block)

    total_in = sum(e.raw.get("usage", {}).get("input_tokens", 0) for e in turn.assistant_events)
    total_out = sum(e.raw.get("usage", {}).get("output_tokens", 0) for e in turn.assistant_events)
    if total_in or total_out:
        elements.append(build_note(f"{total_in}+{total_out} tokens"))

    header = build_header(title=f"🤖 Claude · {project_name}")
    return build_card(header=header, elements=elements)
