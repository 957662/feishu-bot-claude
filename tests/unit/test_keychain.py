"""Tests for KeychainStore abstraction with in-memory fake."""

import pytest

from feishu_bot_claude.config.keychain import InMemoryKeychainStore, KeychainStore


def test_in_memory_store_put_and_get():
    store: KeychainStore = InMemoryKeychainStore()
    store.put("svc.alpha", "secret-1")
    assert store.get("svc.alpha") == "secret-1"


def test_in_memory_store_get_missing_returns_none():
    store = InMemoryKeychainStore()
    assert store.get("nonexistent") is None


def test_in_memory_store_overwrites():
    store = InMemoryKeychainStore()
    store.put("svc.alpha", "v1")
    store.put("svc.alpha", "v2")
    assert store.get("svc.alpha") == "v2"


def test_in_memory_store_delete():
    store = InMemoryKeychainStore()
    store.put("svc.alpha", "secret-1")
    store.delete("svc.alpha")
    assert store.get("svc.alpha") is None


def test_in_memory_store_delete_missing_is_noop():
    store = InMemoryKeychainStore()
    store.delete("nonexistent")  # no raise
