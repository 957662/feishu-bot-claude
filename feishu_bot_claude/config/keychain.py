"""Secret storage abstraction with macOS Keychain backend."""

from __future__ import annotations

from abc import ABC, abstractmethod


class KeychainStore(ABC):
    """Abstract secret store. Backed by macOS Keychain in production."""

    @abstractmethod
    def put(self, key: str, secret: str) -> None:
        """Store or overwrite a secret under `key`."""

    @abstractmethod
    def get(self, key: str) -> str | None:
        """Return the secret for `key`, or None if missing."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete the secret for `key`. No-op if missing."""


class InMemoryKeychainStore(KeychainStore):
    """In-memory store for tests. Not persistent, not secure."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def put(self, key: str, secret: str) -> None:
        self._data[key] = secret

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def delete(self, key: str) -> None:
        self._data.pop(key, None)


class MacOSKeychainStore(KeychainStore):
    """macOS Keychain backend via the `security` command."""

    # Implemented in Task 1.8 — placeholder raises so partial use fails loudly.
    def put(self, key: str, secret: str) -> None:
        raise NotImplementedError("MacOSKeychainStore implemented in Task 1.8")

    def get(self, key: str) -> str | None:
        raise NotImplementedError("MacOSKeychainStore implemented in Task 1.8")

    def delete(self, key: str) -> None:
        raise NotImplementedError("MacOSKeychainStore implemented in Task 1.8")
