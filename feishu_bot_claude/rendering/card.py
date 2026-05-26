"""Atomic Feishu interactive card JSON builders.

Each function returns a single element or a complete card dict. They compose:
build_card(header=..., elements=[build_markdown(...), build_divider(), ...]).
"""

from __future__ import annotations

from typing import Iterable, Literal

Template = Literal["red", "orange", "yellow", "green", "blue", "purple", "indigo", "wathet", "turquoise", "carmine", "violet", "grey"]
ButtonType = Literal["default", "primary", "danger"]


def build_header(title: str, template: Template = "purple") -> dict:
    return {
        "template": template,
        "title": {"tag": "plain_text", "content": title},
    }


def build_markdown(content: str) -> dict:
    return {"tag": "markdown", "content": content}


def build_divider() -> dict:
    return {"tag": "hr"}


def build_note(content: str) -> dict:
    return {
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": content}],
    }


def build_collapsible(summary: str, body_markdown: str, expanded: bool = False) -> dict:
    return {
        "tag": "collapsible_panel",
        "expanded": expanded,
        "header": {
            "title": {"tag": "plain_text", "content": summary},
        },
        "elements": [build_markdown(body_markdown)],
    }


def build_action_buttons(buttons: Iterable[tuple[str, str, ButtonType]]) -> dict:
    """buttons is iterable of (event_key, label, type)."""
    actions = []
    for event_key, label, btn_type in buttons:
        actions.append({
            "tag": "button",
            "text": {"tag": "plain_text", "content": label},
            "type": btn_type,
            "value": {"event_key": event_key},
        })
    return {"tag": "action", "actions": actions}


def build_card(header: dict, elements: list[dict]) -> dict:
    return {
        "schema": "2.0",
        "header": header,
        "elements": elements,
    }
