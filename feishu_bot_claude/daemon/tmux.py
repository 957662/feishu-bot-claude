"""tmux process wrapper: real + fake implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Tmux(ABC):
    """Interface for tmux session management."""

    @abstractmethod
    def has_session(self, name: str) -> bool:
        """Return True if a tmux session with `name` exists."""

    @abstractmethod
    def new_session(self, name: str, cwd: str, command: str, attach_if_exists: bool = False) -> None:
        """Create a new detached tmux session named `name` running `command` in `cwd`.

        If `attach_if_exists` is True and a session with `name` already exists, behaves
        as a no-op (the caller will attach separately).
        If False and the session exists, raises ValueError.
        """

    @abstractmethod
    def send_keys(self, session: str, keys: str) -> None:
        """Send literal keystrokes to the session's primary pane.

        `keys` should include trailing newlines if you want Enter pressed.
        Raises RuntimeError if the session doesn't exist.
        """

    @abstractmethod
    def kill_session(self, name: str) -> None:
        """Kill the session. No-op if missing."""


class FakeTmux(Tmux):
    """In-memory fake — records all calls, lets tests configure session existence."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._sessions: set[str] = set()

    def set_session(self, name: str, exists: bool) -> None:
        """Test helper: set whether a session is considered alive."""
        if exists:
            self._sessions.add(name)
        else:
            self._sessions.discard(name)

    def has_session(self, name: str) -> bool:
        self.calls.append(("has_session", {"name": name}))
        return name in self._sessions

    def new_session(self, name: str, cwd: str, command: str, attach_if_exists: bool = False) -> None:
        if name in self._sessions:
            if attach_if_exists:
                self.calls.append(("attach_session", {"name": name}))
                return
            raise ValueError(f"session {name!r} already exists")
        self.calls.append(("new_session", {"name": name, "cwd": cwd, "command": command}))
        self._sessions.add(name)

    def send_keys(self, session: str, keys: str) -> None:
        if session not in self._sessions:
            raise RuntimeError(f"no session: {session!r}")
        self.calls.append(("send_keys", {"session": session, "keys": keys}))

    def kill_session(self, name: str) -> None:
        self.calls.append(("kill_session", {"name": name}))
        self._sessions.discard(name)
