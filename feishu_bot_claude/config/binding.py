"""BindingConfig dataclass: per-binding configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


_VALID_RENDER_STYLES = {"minimal", "full", "rich"}
_VALID_REPLAY = {"0", "100", "all"}


@dataclass(frozen=True)
class BindingConfig:
    """Configuration for one project ↔ bot binding.

    Frozen because BindingStore returns immutable snapshots; mutations create
    a new BindingConfig and write a fresh TOML file.
    """

    name: str
    project_dir: str
    tmux_session: str
    feishu_app_id: str
    secret_ref: str
    render_style: str = "rich"
    replay_on_start: str = "all"
    mute_thinking: bool = False
    card_throttle_ms: int = 300
    domain: str = "https://open.feishu.cn"
    api_timeout_ms: int = 5000
    upload_timeout_ms: int = 60000
    event_silent_threshold_ms: int = 60000
    event_dead_threshold_ms: int = 120000
    reconnect_grace_failures: int = 3
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("name must be non-empty")
        if not Path(self.project_dir).is_absolute():
            raise ValueError(f"project_dir must be absolute: {self.project_dir!r}")
        if self.render_style not in _VALID_RENDER_STYLES:
            raise ValueError(
                f"render_style must be one of {sorted(_VALID_RENDER_STYLES)}, "
                f"got {self.render_style!r}"
            )
        if self.replay_on_start not in _VALID_REPLAY:
            raise ValueError(
                f"replay_on_start must be one of {sorted(_VALID_REPLAY)}, "
                f"got {self.replay_on_start!r}"
            )
        for fname in ("api_timeout_ms", "upload_timeout_ms", "card_throttle_ms",
                      "event_silent_threshold_ms", "event_dead_threshold_ms",
                      "reconnect_grace_failures"):
            value = getattr(self, fname)
            if value < 0:
                raise ValueError(f"{fname} must be non-negative, got {value}")
