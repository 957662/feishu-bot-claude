"""Smoke test: package can be imported and exposes version."""

import feishu_bot_claude


def test_package_exposes_version():
    assert feishu_bot_claude.__version__ == "0.1.0"
