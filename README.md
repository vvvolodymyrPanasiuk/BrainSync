# 🧠 BrainSync

**A local AI-powered personal knowledge management system.**

Send a message to your Telegram bot → Claude AI classifies and formats it → a structured Markdown note appears in your Obsidian vault. That's it.

BrainSync runs as a background service on your machine. Everything stays local except the AI API call. No cloud storage, no subscriptions, no web dashboard — just your thoughts, organized automatically.

---

## Why BrainSync?

Most note-taking friction happens at capture time. You have a thought, but turning it into a structured note requires opening an app, picking a folder, writing frontmatter, linking related notes — so you skip it, or dump it in an inbox that never gets processed.

BrainSync removes that friction completely:

- **You write one message** in Telegram (where you already are)
- **AI does the organizing** — detects the topic, picks the right folder, formats the content
- **A properly structured note** appears in your Obsidian vault instantly

No manual filing. No inbox to process later. Notes are organized at the moment of capture.

---

## Features

- **Telegram → Obsidian** — plain text in, structured `.md` note out
- **AI classification** — Claude automatically detects type (note / task / idea / journal), topic, and destination folder
- **Three processing modes** — `minimal` (fast, 0–1 AI calls), `balanced` (1–2), `full` (2–3 + auto wikilinks)
- **Map of Content (MoC)** — index files auto-updated when new notes are added to a topic
- **Vault search** — `/search Redis` returns matching notes with excerpts, zero AI calls
- **Scheduled digests** — daily, weekly, and monthly summaries sent automatically to Telegram
- **Git sync** — vault auto-committed and pushed after every note
- **MCP server** — `vault_writer/server.py` registers as an MCP server in Claude Code sessions
- **Inline prefixes** — `task: buy milk` or `задача: купити молоко` without a slash command

---

## Quick Start

### Prerequisites

- [Python 3.12+](https://python.org/downloads) — check "Add Python to PATH" during installation
- [Git](https://git-scm.com)
- An existing [Obsidian](https://obsidian.md) vault (e.g. `C:\SecondaryBrain`)
- A Telegram bot token — create one via [@BotFather](https://t.me/BotFather)
- Your Telegram user ID — get it from [@userinfobot](https://t.me/userinfobot)
- An [Anthropic API key](https://console.anthropic.com)

---

### Option A — One-click install (recommended)

```bash
git clone https://github.com/vvvolodymyrPanasiuk/BrainSync.git
cd BrainSync
```

Then double-click **`install.bat`** (Windows) or run **`bash install.sh`** (macOS / Linux).

The script will:
1. Check that Python is available
2. Install [`uv`](https://github.com/astral-sh/uv) — a fast Python package manager (if not already installed)
3. Install all dependencies into an isolated environment
4. Launch the interactive setup wizard — enter your vault path, bot token, user ID, and API key

That's it. From now on, just run **`start.bat`** to launch the bot.

---

### Option B — Manual install

If you prefer to do it step by step:

```bash
# 1. Clone
git clone https://github.com/vvvolodymyrPanasiuk/BrainSync.git
cd BrainSync

# 2. Install uv (fast package manager — replaces pip + venv)
pip install uv

# 3. Install dependencies (uv creates the virtual environment automatically)
uv sync

# 4. Run the interactive setup wizard
uv run python setup.py
```

### Running the bot

```bash
# Windows
start.bat

# macOS / Linux
bash start.sh

# Or directly (if you used manual install)
uv run python main.py
```

The bot runs in the foreground. Press `Ctrl+C` to stop.

> **What is `uv`?** It's a modern Python package manager that replaces `pip` + `venv`. Running `uv sync` automatically creates an isolated environment for this project and installs all dependencies — no manual activation needed. `uv run` executes any command inside that environment.

---

## Bot Commands

| Command | Description |
|---------|-------------|
| `/note <text>` | Save a note |
| `/task <text>` | Save a task |
| `/idea <text>` | Save an idea |
| `/journal <text>` | Save a journal entry |
| `/search <query>` | Search the vault |
| `/mode minimal\|balanced\|full` | Change processing mode |
| `/status` | Show bot status and session stats |
| `/help` | List all commands |

**Inline prefixes** — no slash command needed:

```
note: ...       нотатка: ...
task: ...       задача: ...     todo: ...
idea: ...       ідея: ...
journal: ...    день: ...
```

Any plain message without a prefix is automatically classified by AI.

**Example session:**

```
You:  learned that CQRS separates read and write models
Bot:  ✓ Saved → Architecture/0004 CQRS pattern.md

You:  /task buy groceries
Bot:  ✓ Saved → Tasks/0012 buy groceries.md

You:  /search Redis
Bot:  🔍 Found 2 notes for "Redis":
      1. Architecture/0003 Redis caching.md
         ...Redis is used for session caching...

You:  /mode full
Bot:  ✓ Mode changed to: full
      ⚠️ Takes effect after bot restart.
```

---

## Architecture

### Project structure

```
BrainSync/
│
├── main.py                        # Entry point — starts the Telegram bot
├── setup.py                       # Interactive installer
├── start.bat / start.sh           # Launch scripts
├── config.yaml                    # Generated by setup.py — never committed
│
├── config/
│   └── loader.py                  # Parses config.yaml → AppConfig dataclasses
│                                  # Validation, logging setup, AI provider factory
│
├── vault_writer/                  # Core library — shared by both processes
│   ├── server.py                  # MCP server (standalone process, stdio transport)
│   │
│   ├── ai/
│   │   ├── provider.py            # AIProvider abstract base + ProcessingMode enum
│   │   ├── anthropic_provider.py  # Claude implementation
│   │   ├── ollama_provider.py     # Ollama stub (v1.1)
│   │   ├── classifier.py          # classify() → ClassificationResult
│   │   ├── formatter.py           # format_note() → structured markdown body
│   │   └── enricher.py            # add_wikilinks() — full mode only
│   │
│   ├── vault/
│   │   ├── writer.py              # write_note(), update_moc(), sequential numbering
│   │   ├── reader.py              # read_frontmatter(), read_note_content()
│   │   └── indexer.py             # build_index(), update_index() → VaultIndex
│   │
│   └── tools/                     # MCP tool handlers
│       ├── create_note.py         # Main orchestrator (classify→format→enrich→write→MoC)
│       ├── search_notes.py        # Full-text search (zero AI calls)
│       ├── classify_content.py    # Text classification
│       ├── update_moc.py          # Map of Content updater
│       └── get_vault_index.py     # Vault index snapshot
│
├── telegram/
│   ├── bot.py                     # PTB Application setup + job queue
│   ├── formatter.py               # Message formatters
│   └── handlers/
│       ├── commands.py            # All slash command handlers
│       ├── message.py             # Plain-text handler + prefix detection + retry
│       └── schedule.py            # Daily / weekly / monthly digest jobs
│
├── git_sync/
│   └── sync.py                    # commit_note() + push_if_due()
│
└── .brain/
    ├── AGENTS.md                  # Universal AI instructions for the vault
    └── skills/
        ├── vault-writer.md        # Folder naming, numbering, MoC rules
        ├── classifier.md          # Classification guidelines + JSON output format
        └── obsidian-rules.md      # Frontmatter schema, tags, wikilink syntax
```

### Note creation flow

From the moment you send a Telegram message to the moment the file appears in your vault:

```
Telegram message received
         │
         ▼
   auth_check()              Reject unauthorized user IDs silently
         │
         ▼
   detect_prefix()           "task: ..." → NoteType.TASK  (0 AI calls)
         │
         ▼
   [no prefix detected]
   classify()                AI call #1 — type + folder + title
         │
         ▼
   [balanced or full mode]
   format_note()             AI call #2 — structured markdown body
         │
         ▼
   [full mode only]
   add_wikilinks()           AI call #3 — related notes from vault index
         │
         ▼
   write_note()              File written under threading.Lock
         │
         ▼
   create_moc_if_missing()
   update_moc()              Appends "- [[0004 Title]]" to ## 🔑 Main sections
         │
         ▼
   update_index()            O(1) in-memory VaultIndex update
         │
         ▼
   commit_note()             git commit (if enabled)
         │
         ▼
   "✓ Saved → Architecture/0004 CQRS pattern.md"
```

### Two independent processes

BrainSync runs as two separate processes that both use `vault_writer/` as a shared Python library:

```
┌──────────────────────────────┐     ┌──────────────────────────────┐
│   main.py                    │     │   vault_writer/server.py     │
│   (Telegram bot)             │     │   (MCP server)               │
│                              │     │                              │
│   run_polling()              │     │   stdio transport            │
│   message handlers           │     │   5 MCP tools                │
│   scheduled jobs             │     │   started by Claude Code     │
│                              │     │                              │
│   imports vault_writer/      │     │   imports vault_writer/      │
│   directly as library        │     │   directly as library        │
└──────────────────────────────┘     └──────────────────────────────┘
```

> **Why two processes?** The MCP SDK's stdio transport takes ownership of stdin/stdout, which is incompatible with PTB's `run_polling()` event loop in the same process. Keeping them separate is simpler than any workaround — and both components share the same `vault_writer/` library with no IPC needed.

---

### Component communication

```
                        YOU
                         │
               ┌─────────┴──────────┐
               │ write a message     │
               │ or /command         │
               └─────────┬──────────┘
                         │  Telegram API
                         ▼
               ┌──────────────────────────────┐
               │        main.py               │
               │      Telegram Bot            │
               │                              │
               │  handlers/message.py         │
               │  handlers/commands.py        │
               │  handlers/schedule.py        │
               └───────────┬──────────────────┘
                           │ calls directly
                           ▼
               ┌──────────────────────────────┐
               │     vault_writer/            │  ← shared Python library
               │                              │
               │  tools/create_note.py        │  orchestrates everything
               │       │                      │
               │       ├── ai/classifier.py   │──── Anthropic API
               │       ├── ai/formatter.py    │──── Anthropic API
               │       ├── ai/enricher.py     │  (full mode only)
               │       │                      │
               │       ├── vault/writer.py    │──── Obsidian vault (disk)
               │       ├── vault/indexer.py   │──── Obsidian vault (disk)
               │       └── vault/reader.py    │──── Obsidian vault (disk)
               │                              │
               │  tools/search_notes.py       │──── Obsidian vault (disk)
               └──────────────────────────────┘
                           │
                           ▼
               ┌──────────────────────────────┐
               │       git_sync/sync.py       │──── Git remote (GitHub etc.)
               └──────────────────────────────┘


  Separately — started by Claude Code, not by main.py:

               ┌──────────────────────────────┐
               │   vault_writer/server.py     │
               │      MCP Server              │
               │                              │
               │  same tools/, ai/, vault/    │──── Obsidian vault (disk)
               │  as above                    │──── Anthropic API
               └──────────┬───────────────────┘
                          │  stdio (MCP protocol)
                          ▼
               ┌──────────────────────────────┐
               │       Claude Code            │
               │   (your coding session)      │
               └──────────────────────────────┘
```

**In plain words:**
- Your message travels from Telegram → bot handlers → `create_note` orchestrator
- The orchestrator calls AI (if needed), writes the file, updates the MoC index, then triggers a git commit
- The MCP server is a completely separate process that exposes the same vault operations to Claude Code via the MCP protocol
- The Obsidian vault is just a folder on disk — both processes read and write `.md` files directly, no Obsidian app required

---

## Configuration

`config.yaml` is generated by `python setup.py` and is **never committed to git**. Below is the full reference.

### AI settings

```yaml
ai:
  provider: "anthropic"           # "anthropic" | "ollama" (ollama planned for v1.1)
  model: "claude-sonnet-4-6"      # Model ID used for all AI calls
  ollama_url: "http://localhost:11434"
  processing_mode: "balanced"     # See processing modes table below
  agents_file: ".brain/AGENTS.md" # Universal AI instructions injected into every prompt
  skills_path: ".brain/skills/"   # Folder containing skill-specific instructions
  inject_vault_index: true        # Pass known topics to AI during classification
  max_context_tokens: 4000        # Token budget for vault context in prompts
  api_key: ""                     # ⚠️  Never logged, never committed, never sent to AI as content
```

**Processing modes:**

| Mode | AI calls | What happens |
|------|----------|--------------|
| `minimal` | 0–1 | Classification only (skipped if prefix is detected) |
| `balanced` | 1–2 | Classification + content formatting |
| `full` | 2–3 | Classification + formatting + wikilink enrichment |

Change mode at runtime with `/mode balanced` — the bot writes `config.yaml` immediately and confirms. The new mode takes effect after the next restart.

### Vault settings

```yaml
vault:
  path: "C:\\SecondaryBrain"      # Absolute path to your Obsidian vault directory
  language: "uk"                  # Language hint passed to AI formatting prompts
```

### Enrichment settings

```yaml
enrichment:
  add_wikilinks: true             # Auto-add wikilinks to related notes (full mode only)
  update_moc: true                # Append wikilink to parent MoC after every note
  max_related_notes: 5            # Maximum wikilinks injected in full mode
  scan_vault_on_start: true       # Rebuild the in-memory vault index at startup
```

### Telegram settings

```yaml
telegram:
  bot_token: ""                   # ⚠️  Never logged
  allowed_user_ids: [123456789]   # Only these Telegram user IDs can interact with the bot
```

If `allowed_user_ids` is empty, the bot logs a warning and rejects every message.

### Inline prefix settings

```yaml
prefixes:
  note:    ["нотатка:", "note:"]
  task:    ["задача:", "task:", "todo:"]
  idea:    ["ідея:", "idea:"]
  journal: ["день:", "journal:"]
```

Matching is case-insensitive. Add or remove prefixes as you like.

### Git sync settings

```yaml
git:
  enabled: true
  auto_commit: true
  commit_message: "vault: auto-save {date} {time}"
  push_remote: true
  remote: "origin"
  branch: "main"
  push_interval_minutes: 30       # Push at most once every 30 minutes
```

Push failures are silent — the bot logs a warning and continues. Your notes are always saved locally even if the remote is unreachable.

### Scheduled digest settings

```yaml
schedule:
  daily_summary:
    enabled: true
    time: "21:00"                 # HH:MM in local time
  weekly_review:
    enabled: true
    day: "sunday"                 # monday … sunday
    time: "20:00"
  monthly_review:
    enabled: true
    day: 1                        # Day of month: 1–28
    time: "10:00"
```

- **Daily digest** — today's notes + all pending tasks (`- [ ] ...` items across task-type notes)
- **Weekly review** — note count grouped by topic for the past week
- **Monthly review** — notes added this month + new topics introduced

### Logging settings

```yaml
logging:
  level: "info"                   # "debug" | "info" | "warn" | "error"
  log_to_file: true
  log_path: "logs/vault.log"
  log_ai_decisions: true          # Logs: type + folder + confidence only — never note content
```

---

## Note format in the vault

Every note written by BrainSync follows this structure:

```markdown
---
title: "CQRS Pattern"
date: 2026-03-30
categories: [Architecture]
tags: [areas/architecture, types/notes]
MoC: "[[0 Architecture]]"
---

## Description

CQRS (Command Query Responsibility Segregation) separates the read and write models
of an application. Commands mutate state, queries return data — never both.

## Conclusions

Use CQRS when read and write operations have significantly different performance
or scaling requirements. Pairs naturally with Event Sourcing.

## Links

- [[0003 Event Sourcing]]
- [[0001 DDD Basics]]
```

**File naming:** `NNNN Title.md` — 4-digit zero-padded sequential number within the folder.
**MoC files:** `0 TopicName.md` — always at the root of their folder, never counted as regular notes.

**Task items** use [Obsidian Tasks](https://github.com/obsidian-tasks-group/obsidian-tasks) format:
```
- [ ] Pending task
- [x] Completed task
```

---

## Using as a Claude Code MCP Server

`vault_writer/server.py` can be registered as an MCP server in any Claude Code project, letting you create and search vault notes directly from a coding session.

Add to `.claude/mcp_servers.json` in your project:

```json
{
  "mcpServers": {
    "vault-writer": {
      "command": "python",
      "args": ["C:/Projects/BrainSync/vault_writer/server.py"]
    }
  }
}
```

Available tools:

| Tool | Description |
|------|-------------|
| `create_note` | Create a note (classify → format → write → update MoC) |
| `search_notes` | Full-text search across the vault |
| `classify_content` | Classify text and return type, folder, and title |
| `update_moc` | Manually update a Map of Content file |
| `get_vault_index` | Get a snapshot of the current vault index |

---

## Security

- `config.yaml` is in `.gitignore` and will never be committed
- `api_key` and `bot_token` are never written to logs, console output, or AI prompts
- `log_ai_decisions: true` logs only `type`, `folder`, and `confidence` — never the content of your notes
- The bot only responds to user IDs listed in `allowed_user_ids`
- Unauthorized access attempts are logged at `warn` level (user ID + timestamp only)

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `python-telegram-bot >= 20.0` | Async Telegram bot framework with built-in job scheduler |
| `anthropic` | Official Claude AI SDK |
| `mcp` | Model Context Protocol server (stdio transport) |
| `pyyaml` | Read and write `config.yaml` |
| `gitpython` | Programmatic git operations on the vault |
| `pytest` | Testing |
