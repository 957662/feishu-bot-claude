"""IPC protocol types — request/response dataclasses with JSON roundtrip."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Request:
    """A single CLI → daemon request line."""

    op: str
    args: dict[str, Any] = field(default_factory=dict)
    request_id: str = ""

    def to_json_line(self) -> str:
        """Serialize to a single line of JSON (no trailing newline)."""
        return json.dumps(asdict(self), separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def from_json_line(cls, line: str) -> Request:
        """Parse one JSON line into a Request."""
        data = json.loads(line)
        return cls(
            op=data["op"],
            args=data.get("args", {}),
            request_id=data.get("request_id", ""),
        )
