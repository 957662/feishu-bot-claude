"""Tests for IPC protocol types."""

import json

import pytest

from feishu_bot_claude.proto import Request


def test_request_serializes_to_json_line():
    """A Request can be serialized to a single-line JSON string."""
    req = Request(op="bind", args={"name": "foo-bot", "cwd": "/x/y"}, request_id="r-1")
    line = req.to_json_line()
    assert "\n" not in line
    parsed = json.loads(line)
    assert parsed == {
        "op": "bind",
        "args": {"name": "foo-bot", "cwd": "/x/y"},
        "request_id": "r-1",
    }


def test_request_parses_from_json_line():
    """A JSON line round-trips into an equivalent Request."""
    line = '{"op": "list", "args": {}, "request_id": "r-2"}'
    req = Request.from_json_line(line)
    assert req.op == "list"
    assert req.args == {}
    assert req.request_id == "r-2"


def test_request_roundtrip():
    """Serializing then parsing produces an equal Request."""
    original = Request(op="start", args={"cwd": "/p"}, request_id="r-3")
    restored = Request.from_json_line(original.to_json_line())
    assert restored == original
