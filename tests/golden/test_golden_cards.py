"""Golden-file tests: each fixture jsonl should render to a stored expected card JSON."""

import json
from pathlib import Path

import pytest

from feishu_bot_claude.rendering.turn import JsonlEvent, group_into_turns
from feishu_bot_claude.rendering.card import build_card, build_header, build_markdown, build_note
from feishu_bot_claude.rendering.tools import render_tool_block

FIXTURES_DIR = Path(__file__).parent / "fixtures"
EXPECTED_DIR = Path(__file__).parent / "expected"


def render_turn_to_card(turn, project_name: str = "test-project", render_style: str = "rich") -> dict:
    """Reference implementation: turn → card JSON. Promoted from this test into
    `rendering/turn.py` as a real function in Task 4.6.
    """
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


def _load_or_write_golden(name: str, actual: dict, write: bool = False) -> dict | None:
    """Load expected/<name>.card.json; if write=True or missing, write the actual."""
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)
    path = EXPECTED_DIR / f"{name}.card.json"
    if write or not path.exists():
        path.write_text(json.dumps(actual, ensure_ascii=False, indent=2), encoding="utf-8")
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", [
    "turn_simple",
    "turn_with_read",
    "turn_with_bash_long",
    "turn_with_subagent",
])
def test_golden_card(name, request):
    """Render fixture jsonl and compare to expected golden JSON."""
    fixture = FIXTURES_DIR / f"{name}.jsonl"
    events = list(JsonlEvent.load_file(fixture))
    turns = group_into_turns(events)
    assert turns, f"{name}: no turns produced"
    actual = render_turn_to_card(turns[-1], project_name="test-project")

    if request.config.getoption("--update-golden", default=False):
        _load_or_write_golden(name, actual, write=True)
        return

    expected = _load_or_write_golden(name, actual, write=False)
    if expected is None:
        pytest.fail(f"No golden file for {name}. Auto-created — re-run to verify.")
    assert actual == expected, (
        f"{name}: rendered card differs from golden.\n"
        f"Run with --update-golden to accept the new output."
    )
