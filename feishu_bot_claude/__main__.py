"""Module entry: `python -m feishu_bot_claude {daemon|<cli-op>}`.

When invoked with `daemon` it starts the server. Otherwise it delegates to
the Click CLI (so `python -m feishu_bot_claude ping` works just like
`feishu-bot-claude ping`).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from feishu_bot_claude.daemon import serve

_DEFAULT_DATA_DIR = Path.home() / ".feishu-bot-claude"


async def _run_daemon() -> None:
    socket_path = Path(os.environ.get(
        "FEISHU_BOT_CLAUDE_SOCKET",
        _DEFAULT_DATA_DIR / "control.sock",
    ))
    bindings_path = Path(os.environ.get(
        "FEISHU_BOT_CLAUDE_BINDINGS",
        _DEFAULT_DATA_DIR / "bindings.toml",
    ))
    server = await serve(socket_path=socket_path, bindings_path=bindings_path)
    try:
        async with server:
            await server.serve_forever()
    except asyncio.CancelledError:
        pass


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "daemon":
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s")
        try:
            asyncio.run(_run_daemon())
        except KeyboardInterrupt:
            pass
        return 0
    # Delegate to Click CLI
    from feishu_bot_claude.cli import main as click_main
    click_main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
