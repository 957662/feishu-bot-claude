"""Per-binding coroutine group lifecycle."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from feishu_bot_claude.config.binding import BindingConfig, BindingStore
from feishu_bot_claude.daemon.feishu import LarkCli
from feishu_bot_claude.daemon.inbound import InboundPipeline
from feishu_bot_claude.daemon.outbound import OutboundPipeline
from feishu_bot_claude.daemon.ratelimit import TokenBucket
from feishu_bot_claude.daemon.state import BindingRuntimeState
from feishu_bot_claude.daemon.tmux import Tmux

logger = logging.getLogger(__name__)


@dataclass
class RunningBinding:
    """Live state of one binding that's actively mirroring."""

    config: BindingConfig
    state: BindingRuntimeState
    outbound: OutboundPipeline
    inbound: InboundPipeline
    tasks: list[asyncio.Task] = field(default_factory=list)


class Orchestrator:
    """Owns per-binding coroutine groups; lifecycle is start/stop per cwd."""

    def __init__(
        self,
        store: BindingStore,
        tmux_factory: Callable[[str], Tmux],
        lark_factory: Callable[[BindingConfig], LarkCli],
        data_dir: Path,
    ) -> None:
        self._store = store
        self._tmux_factory = tmux_factory
        self._lark_factory = lark_factory
        self._data_dir = Path(data_dir)
        self._running: dict[str, RunningBinding] = {}
        self._chat_id_for: dict[str, str] = {}

    def set_chat_id(self, binding_name: str, chat_id: str) -> None:
        """Test/wiring helper: tell the orchestrator which chat_id to send to."""
        self._chat_id_for[binding_name] = chat_id

    def get_running(self, name: str) -> RunningBinding | None:
        return self._running.get(name)

    def list_running(self) -> list[str]:
        return sorted(self._running.keys())

    async def start_binding(self, cwd: str, jsonl_path: Path | None = None) -> RunningBinding:
        cfg = self._store.find_by_cwd(cwd)
        if cfg is None:
            raise KeyError(f"no binding for cwd {cwd!r}")
        if cfg.name in self._running:
            raise RuntimeError(f"binding {cfg.name!r} is already running")

        tmux = self._tmux_factory(cfg.name)
        if not tmux.has_session(cfg.tmux_session):
            raise RuntimeError(
                f"tmux session {cfg.tmux_session!r} is not running — start Claude first"
            )

        lark = self._lark_factory(cfg)
        state_path = self._data_dir / f"state-{cfg.name}.json"
        state = BindingRuntimeState.load(cfg.name, state_path)

        bucket = TokenBucket(rate_per_sec=10, capacity=20)

        if jsonl_path is None:
            jsonl_path = self._guess_jsonl_path(cfg)

        chat_id = self._chat_id_for.get(cfg.name, "")
        outbound = OutboundPipeline(
            jsonl_path=jsonl_path,
            chat_id=chat_id,
            project_name=cfg.name,
            state=state,
            lark=lark,
            bucket=bucket,
            render_style=cfg.render_style,
        )
        inbound = InboundPipeline(
            tmux_session=cfg.tmux_session,
            tmux=tmux,
            lark=lark,
        )

        # Initial backlog process
        await outbound.process_backlog()

        running = RunningBinding(config=cfg, state=state, outbound=outbound, inbound=inbound)

        # Long-running tasks
        running.tasks.append(asyncio.create_task(
            self._outbound_loop(running, jsonl_path, state_path),
            name=f"outbound-{cfg.name}",
        ))
        running.tasks.append(asyncio.create_task(
            self._inbound_loop(running),
            name=f"inbound-{cfg.name}",
        ))
        self._running[cfg.name] = running
        return running

    async def stop_binding(self, cwd: str) -> None:
        cfg = self._store.find_by_cwd(cwd)
        if cfg is None:
            raise KeyError(f"no binding for cwd {cwd!r}")
        running = self._running.pop(cfg.name, None)
        if running is None:
            return
        for task in running.tasks:
            task.cancel()
        for task in running.tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    async def stop_all(self) -> None:
        for name in list(self._running.keys()):
            cfg = self._store.find_by_name(name)
            if cfg:
                await self.stop_binding(cwd=cfg.project_dir)

    def _guess_jsonl_path(self, cfg: BindingConfig) -> Path:
        """Find newest jsonl in ~/.claude/projects/<encoded-cwd>/ — mtime-based."""
        home = Path.home()
        encoded = cfg.project_dir.replace("/", "-").lstrip("-")
        projects_dir = home / ".claude" / "projects" / f"-{encoded}"
        if not projects_dir.exists():
            return projects_dir / "no-session.jsonl"
        candidates = sorted(projects_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[0] if candidates else projects_dir / "no-session.jsonl"

    async def _outbound_loop(self, running: RunningBinding, jsonl_path: Path, state_path: Path) -> None:
        """Watch jsonl, process new bytes on each change, persist state."""
        from feishu_bot_claude.daemon.jsonl_watcher import JsonlWatcher
        watcher = JsonlWatcher(jsonl_path)
        try:
            async for _ in watcher.changes():
                try:
                    await running.outbound.process_backlog()
                    running.state.save(state_path)
                except Exception:
                    logger.exception("outbound process failed for %s", running.config.name)
        except asyncio.CancelledError:
            running.state.save(state_path)
            raise

    async def _inbound_loop(self, running: RunningBinding) -> None:
        try:
            # Real lark-cli streams forever; Fake drains the queue and returns.
            await running.inbound.process_until_idle(max_events=0)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("inbound loop failed for %s", running.config.name)
