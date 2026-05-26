"""BindingConfig dataclass: per-binding configuration."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import tomli_w


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


_DEFAULT_FILE_MODE = 0o600


class BindingStore:
    """TOML-backed store of BindingConfig records.

    File format:
        [[binding]]
        name = "foo-bot"
        project_dir = "/abs/foo"
        ...

    Writes are atomic (write to tempfile, then rename) and enforce 0600 perms.
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._cache: list[BindingConfig] = self._load()

    def all(self) -> list[BindingConfig]:
        return list(self._cache)

    def find_by_name(self, name: str) -> BindingConfig | None:
        return next((b for b in self._cache if b.name == name), None)

    def find_by_cwd(self, cwd: str) -> BindingConfig | None:
        cwd_resolved = str(Path(cwd).resolve())
        return next(
            (b for b in self._cache if str(Path(b.project_dir).resolve()) == cwd_resolved),
            None,
        )

    def add(self, binding: BindingConfig) -> None:
        if self.find_by_name(binding.name) is not None:
            raise ValueError(f"binding {binding.name!r} already exists")
        if self.find_by_cwd(binding.project_dir) is not None:
            raise ValueError(
                f"project_dir {binding.project_dir!r} already bound to a binding"
            )
        self._cache.append(binding)
        self._save()

    def remove(self, name: str) -> None:
        for i, b in enumerate(self._cache):
            if b.name == name:
                del self._cache[i]
                self._save()
                return
        raise KeyError(name)

    def _load(self) -> list[BindingConfig]:
        if not self._path.exists():
            return []
        with self._path.open("rb") as f:
            data = tomllib.load(f)
        return [_dict_to_binding(b) for b in data.get("binding", [])]

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"binding": [_binding_to_dict(b) for b in self._cache]}
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        with tmp.open("wb") as f:
            tomli_w.dump(payload, f)
        os.chmod(tmp, _DEFAULT_FILE_MODE)
        os.replace(tmp, self._path)


def _binding_to_dict(b: BindingConfig) -> dict:
    return {
        "name": b.name,
        "project_dir": b.project_dir,
        "tmux_session": b.tmux_session,
        "feishu_app_id": b.feishu_app_id,
        "secret_ref": b.secret_ref,
        "render_style": b.render_style,
        "replay_on_start": b.replay_on_start,
        "mute_thinking": b.mute_thinking,
        "card_throttle_ms": b.card_throttle_ms,
        "domain": b.domain,
        "api_timeout_ms": b.api_timeout_ms,
        "upload_timeout_ms": b.upload_timeout_ms,
        "event_silent_threshold_ms": b.event_silent_threshold_ms,
        "event_dead_threshold_ms": b.event_dead_threshold_ms,
        "reconnect_grace_failures": b.reconnect_grace_failures,
        "created_at": b.created_at,
    }


def _dict_to_binding(d: dict) -> BindingConfig:
    return BindingConfig(**d)
