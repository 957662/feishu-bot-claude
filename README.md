# feishu-bot-claude

> **让本地的 Claude Code,在飞书里随时随地遥控。**
> 一个项目一个专属机器人,Claude 干的活实时同步到飞书聊天框,你在飞书发的消息也会立刻传给 Claude 执行。

[![Platform](https://img.shields.io/badge/platform-macOS-blue)](https://github.com/957662/feishu-bot-claude)
[![Python](https://img.shields.io/badge/python-3.11%2B-green)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)]()

👉 **Windows 用户**:请使用姊妹仓库 [feishu-bot-claude-windows](https://github.com/957662/feishu-bot-claude-windows)(纯 Windows 原生,不需要 WSL)

---

## 📖 目录

- [它到底是什么](#-它到底是什么)
- [典型使用场景](#-典型使用场景)
- [完整效果演示](#-完整效果演示)
- [整体架构图](#-整体架构图)
- [前置准备](#-前置准备)
- [安装](#-安装)
- [第一次使用:零到能用全流程](#-第一次使用零到能用全流程)
- [日常使用](#-日常使用)
- [常用命令大全](#-常用命令大全)
- [配置项](#-配置项)
- [架构详解(进阶)](#-架构详解进阶)
- [常见问题 FAQ](#-常见问题-faq)
- [故障排查](#-故障排查)
- [开发与测试](#-开发与测试)
- [License](#license)

---

## 🤔 它到底是什么

简单说:**你电脑上的 Claude Code,跟飞书绑定起来**。

打个比方:
- 平时你用 Claude Code,得坐在电脑前的终端里跟它对话
- 现在,你出门遛狗、坐地铁、躺床上,只要打开飞书 App,就能跟你电脑上那个正在跑的 Claude 继续对话
- Claude 在干啥(读文件、改代码、跑命令)你在飞书里看得清清楚楚
- 你想让 Claude 干啥,在飞书里发个消息就行

技术上说:
- 你给某个**项目目录**绑定**一个专属飞书机器人**
- 项目里的 Claude TUI(终端界面)运行时产生的每一轮对话,被实时镜像成飞书的"交互卡片"消息
- 你在飞书里发的消息,被反向注入到那个 TUI 里,Claude 看到就会响应
- 双向打通,**一个项目一个机器人,严格 1 对 1 不串场**

## 🎯 典型使用场景

| 场景 | 怎么用 |
|---|---|
| 🚇 通勤路上,Claude 在公司电脑跑长任务 | 飞书里看进度,需要时插话指挥 |
| 🛋️ 下班想瘫沙发上,但 Claude 还在干活 | 不用打开电脑,手机飞书继续 |
| 🏠 远程办公,临时要让家里电脑跑个调研 | 在公司飞书里直接发任务 |
| 👥 多个项目同时跑 | 每个项目一个机器人,飞书侧边栏自动分流 |

## 🎬 完整效果演示

1️⃣ 你在终端里敲 `claude /bot-new my-project`
```
┌──────────────────────────────────────────┐
│ Claude Code TUI                          │
│ > /bot-new my-project                    │
│ ⚙ 正在创建飞书 App,弹出浏览器扫码...    │
│ ✓ App 创建完成 (cli_aa9f1301ce781cb2)    │
│ ✓ 推送机器人菜单完成                     │
│ ✓ 守护进程已启动,等你给机器人发首条消息 │
└──────────────────────────────────────────┘
```

2️⃣ 你打开飞书,搜到这个机器人,发"你好":
```
┌──── 飞书聊天框 ────────────────┐
│ 你: 你好                       │  ← ❤️ 机器人秒贴心心已读
│                                │
│ 🤖 Claude · my-project         │  ← 整段会话历史自动加载
│ (此处显示之前所有的对话卡片)   │
│ ...                            │
└────────────────────────────────┘
```

3️⃣ 之后随时随地遥控,跟坐在电脑前一模一样:
```
┌──── 飞书聊天框 ────────────────┐
│ 你: 把 user.py 里所有 print 换成 logger.info  │
│                                                 │
│ 🤖 Claude · my-project                          │
│   ▶ 📖 Read  user.py  ✓ 42 lines               │
│   ▶ ✏️ Edit  user.py  ✓                         │
│   完成,替换了 6 处。tests 还需要跑吗?         │
└─────────────────────────────────────────────────┘
```

## 🗺️ 整体架构图

```
┌───────────────────────────────────────────────────────────────────────┐
│                              你的 Mac                                 │
│                                                                       │
│  ┌─────────────────┐                                                  │
│  │ Terminal / iTerm│                                                  │
│  │                 │                                                  │
│  │  tmux session   │                                                  │
│  │ ┌─────────────┐ │                                                  │
│  │ │ Claude Code │◀┼─── send-keys 注入 ──────┐                        │
│  │ │   TUI       │ │                          │                       │
│  │ └──────┬──────┘ │                          │                       │
│  └────────┼────────┘                          │                       │
│           │ 写 jsonl                          │                       │
│           ▼                                   │                       │
│  ~/.claude/projects/<encoded-cwd>/*.jsonl     │                       │
│           │                                   │                       │
│           │ tail -f                           │                       │
│           ▼                                   │                       │
│  ┌──────────────────────────────────────────────────────────┐         │
│  │            feishu-bot-claude daemon                      │         │
│  │           (~/.feishu-bot-claude/control.sock)            │         │
│  │                                                          │         │
│  │   ┌─────────────────┐      ┌─────────────────────────┐  │         │
│  │   │  outbound 流水线 │      │     inbound 流水线      │  │         │
│  │   │                 │      │                         │  │         │
│  │   │ jsonl → turn   │      │ lark-cli event consume  │  │         │
│  │   │   → 渲染卡片    │      │   → event_id 去重       │  │         │
│  │   │   → 速率限制    │      │   → ❤️ reaction ack    │  │         │
│  │   │   → 发送/更新   │      │   → tmux send-keys ────┘  │         │
│  │   └────────┬────────┘      └────────────▲────────────┘  │         │
│  │            │                            │               │         │
│  └────────────┼────────────────────────────┼───────────────┘         │
│               │                            │                          │
│               │ lark-cli messages-send     │ lark-cli event consume   │
│               ▼                            │                          │
│  ┌────────────────────────────────────────┴───────────────┐          │
│  │              lark-cli (npm 全局,Feishu CLI)            │          │
│  └─────────────────────────┬──────────────────────────────┘          │
└────────────────────────────┼─────────────────────────────────────────┘
                             │
                             │ HTTPS
                             ▼
                ┌─────────────────────────────┐
                │   open.feishu.cn (飞书云)    │
                │  - IM API (发卡 / 收消息)   │
                │  - 事件订阅推送(WSS)        │
                └──────────────┬──────────────┘
                               │
                               ▼
                ┌──────────────────────────────┐
                │     飞书 App (你手机/PC)     │
                │   ┌──────────────────────┐   │
                │   │   机器人聊天框      │   │
                │   │ 🤖 my-project        │   │
                │   │                      │   │
                │   │ [卡片] Claude 输出   │   │
                │   │  你的输入...         │   │
                │   └──────────────────────┘   │
                └──────────────────────────────┘
```

**核心思路一句话**:Claude 写 jsonl,daemon tail jsonl → 推飞书;飞书事件推 daemon → tmux 注键。

## 🛠️ 前置准备

要把这套跑起来,你需要:

| 东西 | 是什么 | 怎么装 |
|---|---|---|
| **macOS** | 这个项目只支持 Mac(Windows 用姊妹仓) | — |
| **Python 3.11+** | 写这个工具的语言 | `brew install python@3.12` |
| **Node.js 16+** | 装 `lark-cli` 用 | `brew install node` |
| **tmux** | 终端复用器,Claude 跑在它里面 | `brew install tmux` |
| **Claude Code** | 你要遥控的对象 | [claude.com/code](https://claude.com/code) |
| **飞书账号** | 用来扫码登录、收发消息 | 国内版 `feishu.cn` |
| **飞书开发者权限** | 创建机器人 App 需要 | 默认账号就有 |

> **注**:`lark-cli` 不需要你手动装,`setup.sh` 会跑 `npm i -g @larksuite/cli` 自动装好。

## 📥 安装

```bash
git clone https://github.com/957662/feishu-bot-claude ~/project/feishu-bot-claude
cd ~/project/feishu-bot-claude
./setup.sh
```

`setup.sh` 做了这些事(可以打开脚本看):

| 步骤 | 干了啥 |
|---|---|
| 1 | 在项目目录建 `.venv/` Python 虚拟环境(不污染全局) |
| 2 | `pip install -e .` 装项目依赖 |
| 3 | `npm i -g @larksuite/cli` 装飞书 CLI |
| 4 | 把可执行文件 `feishu-bot-claude` 软链接到 `/opt/homebrew/bin/`(让你全局能调) |
| 5 | 写一份 `~/Library/LaunchAgents/com.qingyun.feishu-bot-claude.plist` 并 load 它(开机自启 daemon) |
| 6 | 把 `commands/bot-*.md` 安装到 `~/.claude/commands/`(让 Claude TUI 里可以用 `/bot-new` 等斜杠命令) |

**装完验证**:

```bash
feishu-bot-claude ping          # 应该返回 OK { "pong": true }
feishu-bot-claude status        # 应该显示 daemon uptime
```

## 🎯 第一次使用:零到能用全流程

下面用一个真实例子走一遍。假设你要给 `~/project/my-app` 这个项目绑机器人。

### Step 1:在项目目录启动 Claude

```bash
cd ~/project/my-app
feishu-bot-claude shell --dangerously-skip-permissions
```

> ⚠️ **关于 `--dangerously-skip-permissions`(危险!全权限模式)**
>
> 这是 Claude Code 官方的"**跳过所有权限确认**"开关。加上它之后:
> - Claude **不会再**对任何动作弹"是否允许?"的确认对话框
> - 删文件 / 改文件 / 跑 shell 命令 / 推 git / `curl ... | bash` 全都**直接执行,无任何拦截**
> - 远程通过飞书发的指令也会被 Claude 直接执行 —— 任何人能给机器人发消息,就能 100% 控制你这台机器
>
> **何时可以加**:
> - ✅ 你在隔离的开发环境 / 临时虚拟机里跑
> - ✅ 你完全信任飞书侧的接收人(默认只有你自己)
> - ✅ 你能容忍 Claude 跑飞之后的代价(代码回滚 / 数据恢复)
>
> **何时绝对不要加**:
> - ❌ 在生产机器 / 装着重要数据的个人主力机上
> - ❌ 飞书机器人聊天框可能被其他人看到或操作(没设 `allow_users` 白名单)
> - ❌ 你不知道这个标志会做什么的时候 —— 先去掉它,Claude 会每次跑命令前问你
>
> 想稳一点就把这个标志删掉,正常跑 `feishu-bot-claude shell` 即可;每次危险操作会在 TUI 里弹确认,你可以在飞书的卡片里看到该提示并通过菜单按钮 / 输入 y/n 来批准。

这条命令会:
- 创建一个 tmux session 名字叫 `claude-my-app`
- 在里面启动 `claude --dangerously-skip-permissions`(如果你加了这个标志)
- 你的当前终端就是 attach 到这个 tmux session 的

如果之前已经跑着了,会直接 attach 进去。

### Step 2:在 Claude TUI 里输入 `/bot-new <名字>`

```
> /bot-new my-app-bot
```

接下来会发生(整个过程~30 秒):
1. 终端里会**自动弹一个浏览器**,显示飞书 OAuth 授权页
2. 用飞书 App 扫码同意,你刚授权的开发者账号会在飞书后台生成一个新 App
3. 终端里继续输出:`✓ App created (cli_xxx)` → `✓ menu pushed` → `✓ binding saved`
4. 显示一句:`等你给机器人发首条消息以 bootstrap`

### Step 3:打开飞书,找到这个机器人

- 飞书 App → 搜索 → 搜你刚才填的 App 名字(`my-app-bot`)
- 你会看到一个新机器人,头像可能还是默认的
- 点进它的聊天框

### Step 4:给它发任意消息(比如"你好")

这条**首条消息**很特殊:
- 它不会被传给 Claude
- 它只是用来**告诉 daemon**:"嘿,这个就是我跟这个机器人的聊天框,记下来"
- daemon 立刻把**当前 Claude 会话的整段历史**渲染成卡片塞进聊天框
- 你能在飞书里看到之前所有对话

> 💡 这一步叫 "bootstrap"(自举)。完成一次后,binding 状态就持久化了,以后 daemon 重启也不用再 bootstrap。

### Step 5:开始遥控

发什么消息,Claude 就会收到什么消息。比如:

> 你:**`帮我把 README 翻译成英文`**
> 🤖 ← ❤️ 已读回执秒贴上
> 🤖 卡片更新:📖 Read README.md → ✏️ Edit README.md → "完成,英文版已写入。"

### Step 6:断开 attach,但保留 session

退出 tmux(`Ctrl+B, D`),回到普通终端。Claude 还在后台跑,飞书侧通讯链路不断。你想再 attach 看 TUI 的话:

```bash
feishu-bot-claude shell --cwd ~/project/my-app
```

## 🔁 日常使用

| 想做啥 | 命令 |
|---|---|
| 看看哪些项目绑了机器人 | `feishu-bot-claude list` |
| 启动 / 重启某个项目的镜像 | `feishu-bot-claude start --cwd <path>` |
| 停止某个项目的镜像 | `feishu-bot-claude stop --cwd <path>` |
| 进 tmux 查看 Claude TUI | `feishu-bot-claude shell --cwd <path>` |
| 看 daemon 是不是活着 | `feishu-bot-claude ping` |
| 看 daemon 日志 | `tail -f ~/.feishu-bot-claude/logs/daemon.err.log` |

## 📚 常用命令大全

### 在 Claude TUI 里(斜杠命令)

| 命令 | 作用 |
|---|---|
| `/bot-new <名字>` | 给当前项目绑一个新机器人 |
| `/bot-list` | 列出所有 binding |
| `/bot-start` | 启动当前项目的镜像 |
| `/bot-stop` | 停止当前项目的镜像 |
| `/bot-config render_style=full` | 调整参数 |
| `/bot-remove <名字>` | 删除 binding(飞书 App 不会被删) |

### 在普通 shell 里(CLI)

```bash
feishu-bot-claude ping                                  # 探活
feishu-bot-claude status                                # 看版本/uptime
feishu-bot-claude list                                  # 列 binding
feishu-bot-claude bind <name> --cwd <path>              # 等价 /bot-new
feishu-bot-claude unbind <name>                         # 等价 /bot-remove
feishu-bot-claude start --cwd <path>                    # 启动镜像
feishu-bot-claude stop --cwd <path>                     # 停止镜像
feishu-bot-claude config --cwd <path> render_style=full # 调参
feishu-bot-claude shell --cwd <path>                    # 起 tmux + Claude
```

## 🔧 配置项

每个 binding 的参数可以单独调,改完会写进 `~/.feishu-bot-claude/bindings.toml`:

| 字段 | 默认 | 含义 |
|---|---|---|
| `render_style` | `rich` | 卡片渲染风格:`minimal` 只文本 / `rich` 含折叠工具块 / `full` 含工具输入 |
| `card_throttle_ms` | `300` | 同一张卡片更新的最小间隔(毫秒) |
| `mute_thinking` | `false` | 是否隐藏 Claude 的 thinking 段 |
| `max_message_length` | `8000` | 飞书入站消息最大字符数,超出截断 |
| `allow_users` | `[]` | 白名单 open_id(空 = 不限制,任何人发都接受) |
| `replay_on_start` | `all` | bootstrap 时回放范围:`all` 全部 / `none` 不回放 |
| `domain` | `https://open.feishu.cn` | 飞书 API 域名(海外版用 `larksuite.com`) |

## 🧠 架构详解(进阶)

### 几个核心概念

| 概念 | 解释 |
|---|---|
| **Binding** | 一个 `(项目目录, 飞书 App, tmux session)` 三元组,持久化在 `bindings.toml` |
| **Bootstrap** | 用户给机器人发首条消息触发,daemon 记下 `chat_id` 并把会话历史一次性灌入 |
| **Turn** | Claude 的一轮对话(user 消息 + 所有 assistant 输出),作为一张卡片整体发送 |
| **Outbound** | jsonl 文件 tail → 渲染成卡片 → 推送飞书的方向 |
| **Inbound** | 飞书消息 → 注入 tmux → 喂给 Claude 的方向 |

### 卡片渲染策略

为了不超飞书的硬限制(单卡 ≤30 KB、单元素 ≤4 KB、≤50 elements、≤3 tables),outbound 做了这些:

- 一个 turn 攒齐再发,**不按事件刷新**(否则一轮里要刷几十次卡)
- 单 element 字符数硬上限 4000,超了加"…(截断 N 字符)…"
- 一张卡 ≤40 个 elements,超了加"…省略 N 个工具调用/段落…"
- 工具输出预览限制 60 行
- code block 之外的管道符 `|` 自动转义为 `\|`,防止飞书把 markdown 表格解析成 table 元素(table 数量有硬上限)

### 入站去重

飞书事件总线是 **at-least-once** 投递。同一条用户消息可能因为重试推两次。inbound 维护一个 LRU(1024 容量)记最近见过的 `event_id`,重复直接丢弃。

### 速率限制

飞书 app-bot 消息接口大约 50 req/s 的限制。我们用令牌桶限到 **45 req/s, burst 50**,留 10% 余量。

### 进程模型

```
launchd
   └─ python -m feishu_bot_claude daemon          (常驻)
        ├─ asyncio task: outbound watcher * N     (每个 binding 一个)
        ├─ asyncio task: inbound consumer * N     (每个 binding 一个)
        └─ asyncio Unix-socket server             (CLI 通信)
```

设计文档:[`docs/superpowers/specs/2026-05-26-feishu-bot-claude-design.md`](docs/superpowers/specs/2026-05-26-feishu-bot-claude-design.md)

## ❓ 常见问题 FAQ

**Q1: 我能不能不用 macOS Keychain,把密钥存别处?**
A: 暂不行。当前实现写死了 `security` CLI。改的话改 `feishu_bot_claude/config/keychain.py` 加一个 backend。

**Q2: 一个项目可以绑多个机器人吗?**
A: 不行,严格 1:1。但你可以把同一个项目目录复制一份(不同路径),分别绑不同机器人。

**Q3: 我用海外飞书 / Lark 怎么办?**
A: `/bot-config domain=https://open.larksuite.com`,然后重新 bind。

**Q4: 飞书机器人怎么没收到消息?**
A: 看 daemon 日志 `tail -f ~/.feishu-bot-claude/logs/daemon.err.log`。常见原因:bootstrap 没做(没给机器人发过首条消息)、daemon 没启动、tmux session 不存在。

**Q5: 我发的消息 Claude 收到两次?**
A: 不应该发生(已加了 event_id 去重)。如果还有,看日志里 `dropping duplicate event_id` 出现频率;如果没出现,贴 issue。

**Q6: 我能让 Claude 输出短一点吗?**
A: `/bot-config render_style=minimal`,只发文本,不发工具调用细节。

**Q7: 一张卡片为啥不显示了/被截断了?**
A: 飞书有硬限制,我们已经在客户端尽量截了。如果被砍得太狠,可以 `/bot-config render_style=full` 看是否好转,或者改 `feishu_bot_claude/rendering/tools.py` 里的常量(`TOOL_BLOCK_CHAR_LIMIT`、`MAX_ELEMENTS_PER_CARD`)。

## 🩺 故障排查

### daemon 起不来

```bash
launchctl list | grep feishu-bot-claude    # 看是不是 loaded
tail -30 ~/.feishu-bot-claude/logs/daemon.err.log
launchctl unload ~/Library/LaunchAgents/com.qingyun.feishu-bot-claude.plist
launchctl load ~/Library/LaunchAgents/com.qingyun.feishu-bot-claude.plist
```

### `lark-cli` 在 daemon 里找不到

launchd 的 PATH 不继承 shell 的。检查 plist 里 `EnvironmentVariables.PATH` 是不是包含 `/opt/homebrew/bin`。

### 卡片发不出去,飞书返回错误码

| 错误码 | 含义 | 修法 |
|---|---|---|
| `99992402` | uuid > 50 字符 | 升级到最新版,已修 |
| `230025` | 消息体超 30KB | 改 `render_style=minimal` 或缩短 `max_message_length` |
| `230099 / 11310 element` | 单元素超 4KB | 同上 |
| `230099 / 11310 table` | 表格数超 3 | 同上;最新版会自动转义 `\|` |
| `200861 unsupported tag note` | schema 2.0 不支持 note 标签 | 升级到最新版 |
| `11232` | 飞书限流 | 降 `card_throttle_ms` 或减少操作频率 |

## 🧪 开发与测试

```bash
source .venv/bin/activate
pytest --cov=feishu_bot_claude                  # 195+ 测试
pytest tests/unit -q                            # 只跑单测
pytest tests/golden --update-golden -q          # 重新生成 golden 快照
```

测试覆盖了:
- 单测:渲染、配置、协议、handler 逻辑、各种 Fake adapter
- 集成:真 tmux 行为、daemon 子进程往返
- Golden:卡片 JSON 快照,改了渲染就要重跑 `--update-golden`

## License

MIT
