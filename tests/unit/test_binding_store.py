"""Tests for BindingStore: TOML I/O, lookup, lifecycle."""

from datetime import datetime, timezone

import pytest

from feishu_bot_claude.config.binding import BindingConfig, BindingStore


def _make_config(name="foo-bot", project_dir="/abs/foo", **overrides) -> BindingConfig:
    defaults = dict(
        name=name,
        project_dir=project_dir,
        tmux_session=f"claude-{name}",
        feishu_app_id=f"cli_{name}",
        secret_ref=f"feishu-bot-claude.{name}.app_secret",
        created_at=datetime(2026, 5, 26, 18, 50, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return BindingConfig(**defaults)


def test_empty_store_returns_no_bindings(tmp_path):
    store = BindingStore(tmp_path / "bindings.toml")
    assert store.all() == []


def test_add_then_find_by_name(tmp_path):
    store = BindingStore(tmp_path / "bindings.toml")
    cfg = _make_config()
    store.add(cfg)
    assert store.find_by_name("foo-bot") == cfg


def test_find_by_name_returns_none_when_absent(tmp_path):
    store = BindingStore(tmp_path / "bindings.toml")
    assert store.find_by_name("nope") is None


def test_find_by_cwd_returns_matching_binding(tmp_path):
    store = BindingStore(tmp_path / "bindings.toml")
    store.add(_make_config(name="foo-bot", project_dir="/abs/foo"))
    store.add(_make_config(name="bar-bot", project_dir="/abs/bar"))
    found = store.find_by_cwd("/abs/foo")
    assert found is not None
    assert found.name == "foo-bot"


def test_find_by_cwd_returns_none_when_no_match(tmp_path):
    store = BindingStore(tmp_path / "bindings.toml")
    store.add(_make_config(name="foo-bot", project_dir="/abs/foo"))
    assert store.find_by_cwd("/abs/other") is None


def test_add_persists_to_disk(tmp_path):
    path = tmp_path / "bindings.toml"
    store1 = BindingStore(path)
    cfg = _make_config()
    store1.add(cfg)
    store2 = BindingStore(path)
    assert store2.find_by_name("foo-bot") == cfg


def test_remove_deletes_binding(tmp_path):
    store = BindingStore(tmp_path / "bindings.toml")
    store.add(_make_config())
    store.remove("foo-bot")
    assert store.find_by_name("foo-bot") is None
    assert store.all() == []


def test_remove_missing_raises(tmp_path):
    store = BindingStore(tmp_path / "bindings.toml")
    with pytest.raises(KeyError, match="foo-bot"):
        store.remove("foo-bot")


def test_add_duplicate_name_raises(tmp_path):
    store = BindingStore(tmp_path / "bindings.toml")
    store.add(_make_config(name="foo-bot"))
    with pytest.raises(ValueError, match="already exists"):
        store.add(_make_config(name="foo-bot", project_dir="/abs/different"))


def test_add_duplicate_project_dir_raises(tmp_path):
    """Hard invariant: one project dir ↔ one binding."""
    store = BindingStore(tmp_path / "bindings.toml")
    store.add(_make_config(name="foo-bot", project_dir="/abs/foo"))
    with pytest.raises(ValueError, match="project_dir.*already bound"):
        store.add(_make_config(name="another-bot", project_dir="/abs/foo"))


def test_toml_file_has_secure_permissions(tmp_path):
    """bindings.toml must be 0600 after any write."""
    path = tmp_path / "bindings.toml"
    store = BindingStore(path)
    store.add(_make_config())
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600, f"expected 0600, got {oct(mode)}"
