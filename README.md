# feishu-bot-claude

Bridge your local Claude Code TUI to dedicated Feishu (Lark) bots — one bot per project, full bidirectional mirror with native slash command support.

## What it does

- Run `claude` in any project directory.
- Bind it to a dedicated Feishu bot via `/bot-new`.
- Anything you say in the Feishu chat is injected into your local Claude TUI (text or native slash command like `/compact`, `/agents`).
- Anything Claude renders in the TUI (assistant turns, tool calls, results) is mirrored to Feishu as updateable interactive cards.
- Strict 1-bot-per-project isolation — no chance of conversation mix-up.
- Survives daemon restart, network jitter, and macOS Keychain handles your app secrets.

## Quick start

```bash
git clone <repo> ~/project/feishu-bot-claude
cd ~/project/feishu-bot-claude
./setup.sh
cd ~/your-project
feishu-bot-claude shell      # opens tmux + Claude Code
```

Inside Claude TUI:
```
/bot-new my-project-bot      # scan QR with Feishu mobile
/bot-start                   # start mirror
```

See [docs/install.md](docs/install.md) for full install details and troubleshooting.

## Architecture

5 components, ~2k LoC Python:

- **daemon** — async Unix-socket server orchestrating per-binding coroutine groups
- **CLI** — Click-based client (`feishu-bot-claude {ping,list,bind,start,stop,...}`)
- **`.claude/commands/bot-*.md`** — Claude Code user-level slash commands
- **lark-cli** — official Feishu Go binary (Feishu API adapter)
- **tmux** — hosts Claude TUI; daemon `send-keys` injects Feishu messages as keystrokes

Each binding has two pipelines:
- **outbound**: tail Claude jsonl → group into turns → render Feishu cards (rate-limited)
- **inbound**: lark-cli event consume → route text/slash/menu → tmux send-keys

See [docs/superpowers/specs/2026-05-26-feishu-bot-claude-design.md](docs/superpowers/specs/2026-05-26-feishu-bot-claude-design.md) for the full design.

## Phase status

| Phase | Tag | What it adds |
|---|---|---|
| 1 | `phase-1-complete` | Foundation: proto + config storage |
| 2 | `phase-2-complete` | IPC plumbing: daemon socket + CLI |
| 3 | `phase-3-complete` | tmux + lark-cli adapters |
| 4 | `phase-4-complete` | Card rendering + golden tests |
| 5 | `phase-5-complete` | Bidirectional mirror pipelines |
| 6 | `phase-6-complete` | Orchestrator + lifecycle |
| 7 | `phase-7-complete` | OAuth + menu push |
| 8 | `phase-8-complete` | Distribution + setup.sh |
| 9 | `phase-9-complete` | Hardening + state recovery |

## Common commands

| Slash | What |
|---|---|
| `/bot-new <name>` | Bind current project to a new Feishu bot |
| `/bot-list` | Show all bindings |
| `/bot-start` / `/bot-stop` | Control mirror for current project |
| `/bot-config render_style=full` | Tweak parameters |
| `/bot-remove <name>` | Delete a binding (Feishu app stays) |

## Testing

```bash
source .venv/bin/activate
pytest --cov=feishu_bot_claude
```

189+ tests on unit + integration. Real tmux + lark-cli tests skip gracefully on machines without those binaries.

## License

MIT
