# 🧠 BrainSync

**Local AI-powered personal knowledge management via Telegram.**

Send a message, voice note, photo, PDF, or YouTube link → AI classifies, formats, and saves it as a structured Markdown note in your Obsidian vault. Ask questions about your notes in natural language — the bot searches your vault semantically and answers using only your own knowledge. Everything runs locally, nothing leaves your machine except optional AI API calls.

---

## What it does

BrainSync solves two problems: **capture** and **retrieval**.

**Capture** — you have a thought while doing something else. Open Telegram, send a message, and it appears in your vault as a properly formatted note — correct folder, frontmatter, wikilinks to related notes, added to the Map of Content. Zero manual filing.

**Retrieval** — you remember writing something about a topic but can't find it. Ask the bot in plain language: *"що я думав про CQRS?"* — it finds semantically relevant notes and gives you a synthesized answer with citations, even if your notes never contained the exact words you typed.

---

## Features

### Capture

| What you send | What happens |
|---------------|--------------|
| Plain text message | AI semantic router → classifies intent → formats → saves |
| Text with inline prefix (`task:`, `ідея:`) | Forced type, skips AI routing |
| Voice message | On-device transcription (Whisper) → note |
| Photo | AI visual description → note |
| PDF file | Full text extracted locally → note |
| `.txt` / `.md` file | Content saved directly as note |
| YouTube URL | NotebookLM session → Q&A → save to vault |
| Any bare URL | Web page fetched, AI-summarised → note |

### Intelligence

- **AI Semantic Router** — every plain-text message goes through a single AI call that returns an `ActionPlan`: intent, target folder (4-level hierarchy), note type, tags, title, and whether to save, search, or answer.
- **Semantic search** — `/search` and natural language queries use vector embeddings; finds notes by meaning, not exact words. Works in Ukrainian.
- **RAG answers** — questions about your vault get synthesized answers grounded exclusively in your own notes, with source citations.
- **Duplicate detection** — after every note save, checks for semantically similar existing notes (≥ 85% similarity) and offers to merge.
- **Smart note splitting** — if a message covers multiple unrelated topics, AI automatically splits it into separate notes.
- **Web clipping** — paste any URL; the bot fetches the page and AI-summarises it into a structured vault note.
- **YouTube × NotebookLM** — paste a YouTube URL to open an interactive Q&A session powered by NotebookLM; save the session as a vault note when done.
- **Knowledge gap analysis** — `/gaps <topic>` asks AI to identify missing subtopics in your vault for a given subject.

### Vault management

- **Map of Content** — index files auto-updated every time a note is added to a topic
- **4-level folder hierarchy** — `GeneralCategory/Topic/Subtopic/Section`
- **Auto wikilinks** — related notes automatically linked to each other on save
- **Vault health check** — `/health` reports orphan notes, broken links, missing aliases, and potential duplicates
- **Note merge** — merge a new note with an existing duplicate via inline button (with confirmation dialog)
- **Note move** — move notes to different folders via `/move` command or inline button after save
- **Tag management** — add tags to any saved note via inline button
- **Group Topics** — map Telegram Forum Topic threads to vault folders; `/register-topic` once per thread

### Gamification

- **XP system** — earn XP for every note saved
- **Streaks** — daily streak tracking with notifications at 3, 7, 14, 30, 100 days
- **Milestones** — achievements at 10, 25, 50, 100, 250, 500, 1000 notes
- **Levels** — Beginner → Note Taker → Chronicler → Knowledge Builder → Archivist → Vault Master → Grand Sage

### Analytics & Visualization

- **`/stats`** — total notes, per-folder bar chart, 30-day activity line chart, XP/streak; sends as PNG chart if matplotlib installed
- **`/graph`** — knowledge graph PNG showing wikilink connections between notes, colored by folder; requires `networkx` + `matplotlib`
- **Scheduled summaries** — daily text digest; weekly and monthly reports include 2–3 panel PNG charts (notes by topic, daily activity, type breakdown, month-over-month comparison)

### Automation

- **Git sync** — vault auto-committed and pushed after every note (configurable interval)
- **Stale task reminder** — configurable daily reminder for tasks open longer than N days
- **Hot reload** — `/reload` reloads `config.yaml` without restarting the bot
- **MCP server** — exposes vault operations to Claude Code sessions

### UX

- **Progress indicator** — `⏳ Thinking…` message shown during AI processing, deleted when result arrives
- **Inline keyboards** — actionable buttons after every note save: [📁 Move] [🏷️ Tags]; duplicate detected: [🔀 Merge] [✅ Keep both]
- **Merge confirmation** — destructive merge operation always requires [✅ Confirm] [❌ Cancel]
- **`/settings`** — inline keyboard to toggle auto-commit, wikilinks, MoC, daily summary; changes persist to `config.yaml`
- **`/today`** — today's notes + all open tasks at a glance

### Infrastructure

- **Fully offline capable** — sentence-transformers for embeddings, Ollama for AI, Whisper for voice
- **Vector index persists** — ChromaDB stores embeddings in `data/chroma/`; survives restarts
- **Background indexing** — vault indexed at startup without blocking the bot

---

## Prerequisites

1. **Python 3.12+** — [python.org/downloads](https://python.org/downloads). Check "Add Python to PATH" during install on Windows.
2. **Git** — [git-scm.com](https://git-scm.com)
3. **ffmpeg** — required for voice message decoding:
   ```
   winget install ffmpeg        # Windows
   brew install ffmpeg          # macOS
   sudo apt install ffmpeg      # Ubuntu/Debian
   ```
4. **An Obsidian vault** — an existing folder where your `.md` notes live. The Obsidian app does not need to be running.
5. **A Telegram bot** — create via [@BotFather](https://t.me/BotFather), copy the token.
6. **Your Telegram user ID** — get from [@userinfobot](https://t.me/userinfobot).
7. **AI provider** — either:
   - [Anthropic API key](https://console.anthropic.com) (cloud, requires internet)
   - [Ollama](https://ollama.com) running locally (fully offline, free)

**Optional** (for charts and graph):
```bash
pip install networkx matplotlib numpy
```

**Optional** (for YouTube × NotebookLM):
```bash
pip install "notebooklm-py[browser]"
notebooklm login    # one-time Google auth via browser
```

---

## Installation

### Option A: One-click (Windows)

```bash
git clone https://github.com/vvvolodymyrPanasiuk/BrainSync.git
cd BrainSync
```

Double-click **`start.bat`**. The script installs `uv`, creates a virtual environment, installs dependencies, and launches the setup wizard on first run.

### Option B: Manual

```bash
git clone https://github.com/vvvolodymyrPanasiuk/BrainSync.git
cd BrainSync
pip install uv
uv sync
uv run python setup.py    # interactive setup wizard
uv run python main.py
```

---

## First run

`setup.py` will ask:

| Question | Example answer |
|----------|---------------|
| Vault path | `C:\SecondaryBrain` |
| AI provider | `anthropic` or `ollama` |
| API key (if Anthropic) | `sk-ant-...` |
| Telegram bot token | `7123456789:AAF...` |
| Your Telegram user ID | `123456789` |

The wizard creates `config.yaml` (gitignored — never committed).

---

## Bot commands

### Notes

| Command | Description |
|---------|-------------|
| `/note <text>` | Save a note |
| `/task <text>` | Save a task |
| `/idea <text>` | Save an idea |
| `/journal <text>` | Save a journal entry |
| `/clip <url>` | Fetch a web page, AI-summarise, and save as note |

### Vault

| Command | Description |
|---------|-------------|
| `/search <query>` | Semantic vault search |
| `/today` | Today's saved notes + all open tasks |
| `/health` | Vault health check: orphans, broken links, missing aliases, duplicates |
| `/move <topic> -> <folder>` | Move a note to a different folder |
| `/merge` | Merge newest note with detected duplicate (shows confirmation dialog) |
| `/stats` | Vault statistics with bar/line charts (PNG if matplotlib installed) |
| `/graph` | Knowledge graph PNG of wikilink connections (requires networkx + matplotlib) |
| `/gaps <topic>` | AI analysis of missing subtopics in your vault for a given subject |

### Groups & Routing

| Command | Description |
|---------|-------------|
| `/register-topic <FolderName>` | Map current Telegram Forum Topic thread to a vault folder |

### System

| Command | Description |
|---------|-------------|
| `/settings` | Inline settings menu — toggle auto-commit, wikilinks, MoC, daily summary |
| `/status` | Bot status, session stats, AI provider info |
| `/reload` | Hot-reload `config.yaml` without restarting the bot |
| `/reindex` | Rebuild the vector index from all vault notes |
| `/help` | Full command reference |

---

## Inline prefixes

Add a prefix at the start of any message (or media caption) to force a note type:

```
note: ...       нотатка: ...
task: ...       задача: ...     todo: ...
idea: ...       ідея: ...
journal: ...    день: ...
```

Any plain message **without** a prefix or slash command is routed through the AI semantic router.

---

## Media

### Voice messages
Hold mic → BrainSync transcribes on-device via Whisper (Ukrainian supported) → saves as note.
Limit: `media.max_voice_duration_seconds` (default 300s). Whisper `small` model (~466 MB) downloads on first use.

### Photos
BrainSync sends the image to AI for visual description → saves as note.
Requires `ollama_vision_model` (e.g. `llava`) or an Anthropic model.

### PDFs
Full text extracted locally via `pypdf` → first 3 000 chars sent to AI for classification → full text saved to vault.
Limits: `media.pdf_max_pages` (default 50), `media.max_file_size_mb` (default 20).

### Plain text / Markdown files
Attach `.txt` or `.md` → content saved as note directly.

### YouTube URLs
Send a bare YouTube URL → BrainSync creates a NotebookLM notebook, adds the video as source, and enters interactive Q&A mode. Each message in the session is answered by NotebookLM. Press **💾 Save to vault** to save the session as a note; the notebook is deleted after save. Requires `notebooklm-py`.

### Bare URLs (web clip)
Send any `https://...` URL that isn't YouTube → BrainSync fetches the page, extracts text, AI-summarises into a structured note, and saves it.

---

## AI Semantic Router

Every plain-text message (without prefix) goes through a single AI call that returns an `ActionPlan`:

| Field | Example |
|-------|---------|
| `intent` | `CREATE_NOTE`, `ANSWER_FROM_VAULT`, `SEARCH_VAULT`, `MOVE_NOTE`, … |
| `target_folder` | `"Technology/Python"` |
| `note_type` | `"note"`, `"task"`, `"idea"`, `"journal"` |
| `tags` | `["python", "async"]` |
| `title` | `"Asyncio event loop internals"` |
| `should_save` | `true` / `false` |

Intents and what happens:

| Intent | Behaviour |
|--------|-----------|
| `CREATE_NOTE` | Format → enrich with wikilinks → write → MoC → duplicate check |
| `ANSWER_FROM_VAULT` | RAG: vector search → AI synthesizes answer from your notes |
| `SEARCH_VAULT` | Semantic search → ranked results list |
| `CHAT_ONLY` | General conversation, no vault interaction |
| `SEARCH_WEB` | DuckDuckGo search → AI-synthesized answer |
| `MOVE_NOTE` | Find note semantically → move to target folder |
| `APPEND_NOTE` | Find closest note → append content |
| `UPDATE_NOTE` | Find closest note → rewrite with new info |
| `REQUEST_CLARIFICATION` | Ask one follow-up question; next reply resolves the action |
| `IGNORE_SPAM` | Silently discard |

---

## Duplicate detection & merge

After every save, BrainSync checks cosine similarity against existing notes:

- **≥ 85%** — duplicate warning + [🔀 Merge] [✅ Keep both] buttons
- **70–84%** — related note suggestion

Clicking **Merge** shows a confirmation dialog. On confirm, AI merges the two notes (preserves frontmatter from the existing note, deduplicates body), deletes the new file, and updates the vector store.

Thresholds configurable in `config.yaml` under `embedding`.

---

## Gamification

Stored in `<vault>/.brainsync/gamification.json`. Shown in `/stats`.

| Level | XP required |
|-------|-------------|
| Beginner | 0 |
| Note Taker | 100 |
| Chronicler | 300 |
| Knowledge Builder | 600 |
| Archivist | 1 000 |
| Vault Master | 2 000 |
| Grand Sage | 5 000 |

Streak notifications fire at 3, 7, 14, 30, 100 days. Milestone notifications fire at 10, 25, 50, 100, 250, 500, 1 000 notes.

---

## Configuration reference

`config.yaml` is generated by `setup.py` and is never committed.

### AI settings

```yaml
ai:
  provider: "anthropic"           # "anthropic" | "ollama"
  model: "claude-sonnet-4-6"
  ollama_url: "http://localhost:11434"
  ollama_vision_model: ""         # e.g. "llava" — for photo descriptions
  ollama_timeout: 900             # seconds (increase for slow hardware / thinking models)
  agents_file: ".brain/AGENTS.md"
  skills_path: ".brain/skills/"
  inject_vault_index: true
  max_context_tokens: 4000
  api_key: ""                     # Never logged, never committed
```

### Vault settings

```yaml
vault:
  path: "C:\\SecondaryBrain"
  language: "uk"                  # Language hint for AI prompts
```

### Embedding / semantic search

```yaml
embedding:
  backend: "sentence-transformers"          # "sentence-transformers" | "ollama"
  model: "paraphrase-multilingual-MiniLM-L12-v2"
  ollama_embed_url: "http://localhost:11434"
  index_path: "data/chroma"
  similarity_duplicate_threshold: 0.85      # ≥ this → duplicate warning
  similarity_related_threshold: 0.70        # ≥ this → related notice
  top_k_results: 5
```

Use Ollama embeddings (fully offline):
```bash
ollama pull nomic-embed-text
```
Then set `backend: "ollama"` and `model: "nomic-embed-text"`, run `/reindex`.

### Media settings

```yaml
media:
  max_voice_duration_seconds: 300
  transcription_model: "small"    # tiny / base / small / medium / large-v3
  pdf_max_pages: 50
  pdf_ai_context_chars: 3000
  max_file_size_mb: 20
```

| Whisper model | Size | Accuracy |
|---------------|------|----------|
| `tiny` | ~75 MB | Low |
| `base` | ~145 MB | OK |
| `small` | ~466 MB | Good (default) |
| `medium` | ~1.5 GB | Very good |
| `large-v3` | ~3 GB | Best |

### Enrichment settings

```yaml
enrichment:
  add_wikilinks: true
  update_moc: true
  max_related_notes: 5
  scan_vault_on_start: true
```

### Telegram settings

```yaml
telegram:
  bot_token: ""
  allowed_user_ids: [123456789]
```

### Git settings

```yaml
git:
  enabled: true
  auto_commit: true
  commit_message: "vault: auto-save {date} {time}"
  push_remote: true
  remote: "origin"
  branch: "main"
  push_interval_minutes: 30
```

### Schedule settings

```yaml
schedule:
  daily_summary:
    enabled: true
    time: "21:00"             # Plain text digest: today's notes + open tasks
  weekly_review:
    enabled: true
    day: "sunday"
    time: "20:00"             # PNG chart: notes by topic + daily activity
  monthly_review:
    enabled: true
    day: 1
    time: "10:00"             # PNG chart: this vs last month + types pie + activity
  stale_task_reminder:
    enabled: false
    days: 7                   # Remind about tasks open longer than N days
    time: "09:00"
```

### Prefix settings

```yaml
prefixes:
  note:    ["нотатка:", "note:"]
  task:    ["задача:", "task:", "todo:"]
  idea:    ["ідея:", "idea:"]
  journal: ["день:", "journal:"]
```

### Logging settings

```yaml
logging:
  level: "info"
  log_path: "logs/vault.log"
  log_ai_decisions: true      # Logs type + folder + confidence only — never note content
```

---

## Note format

Every note created by BrainSync:

```markdown
---
title: "CQRS Pattern"
date: 2026-03-30
categories: [Architecture]
tags:
  - areas/architecture
  - types/note
MoC: "[[0 Architecture]]"
aliases:
  - CQRS Pattern
---

## Description

CQRS (Command Query Responsibility Segregation) separates the read and write
models of an application. Commands mutate state, queries return data.

## Conclusions

Use CQRS when read and write operations have significantly different scaling
requirements. Pairs naturally with Event Sourcing.

## Links

- [[0003 Event Sourcing]]
- [[0001 DDD Basics]]
```

**Naming:** `NNNN Title.md` — 4-digit zero-padded sequential number per folder.
**Location:** `<vault>/<GeneralCategory>/<Topic>/<Subtopic>/<Section>/_data/NNNN Title.md`
**MoC files:** `0 TopicName.md` — auto-created at each folder level.

---

## Running fully offline

1. Install and start [Ollama](https://ollama.com)
2. Pull models:
   ```bash
   ollama pull mistral
   ollama pull llava                # for photo descriptions
   ollama pull nomic-embed-text     # optional: Ollama embeddings
   ```
3. In `config.yaml`:
   ```yaml
   ai:
     provider: "ollama"
     model: "mistral"
     ollama_vision_model: "llava"
   embedding:
     backend: "sentence-transformers"   # works offline
   ```

Whisper voice transcription is always offline regardless of AI provider.

---

## Project structure

```
BrainSync/
│
├── main.py                        # Entry point — starts the Telegram bot
├── setup.py                       # Interactive installer / config wizard
├── start.bat / start.sh           # Launch scripts
├── config.yaml                    # Generated by setup.py — gitignored
│
├── config/
│   └── loader.py                  # config.yaml → AppConfig dataclasses + validation
│
├── vault_writer/                  # Core library
│   ├── server.py                  # MCP server (standalone process, stdio transport)
│   │
│   ├── ai/
│   │   ├── provider.py            # AIProvider ABC
│   │   ├── anthropic_provider.py  # Claude text + vision
│   │   ├── ollama_provider.py     # Ollama text + vision
│   │   ├── transcriber.py         # Whisper on-device voice transcription
│   │   ├── router.py              # AI Semantic Router → ActionPlan (single AI call)
│   │   ├── classifier.py          # ClassificationResult for legacy path
│   │   ├── formatter.py           # format_note() → structured markdown
│   │   ├── enricher.py            # AI-powered content enrichment
│   │   └── linker.py              # Wikilink injection + retroactive linking
│   │
│   ├── rag/
│   │   ├── embedder.py            # EmbeddingProvider (sentence-transformers + Ollama)
│   │   ├── vector_store.py        # ChromaDB wrapper (upsert, search, find_similar)
│   │   └── engine.py              # answer_query(), search_vault()
│   │
│   ├── vault/
│   │   ├── writer.py              # write_note(), update_moc(), sequential numbering
│   │   ├── indexer.py             # build_index(), update_index() → VaultIndex
│   │   └── structure.py           # Folder registration
│   │
│   └── tools/
│       ├── create_note.py         # Orchestrator: classify→format→enrich→write→MoC→upsert
│       ├── executor.py            # ActionPlan executor (all intents)
│       ├── gamification.py        # XP, streaks, milestones, levels
│       ├── health.py              # Vault health check (orphans, broken links, duplicates)
│       ├── web_clip.py            # URL fetcher + text extractor
│       ├── search_notes.py        # Keyword full-text search
│       ├── update_moc.py          # Map of Content updater
│       └── get_vault_index.py     # Vault index snapshot
│
├── telegram/
│   ├── bot.py                     # PTB Application setup, all handler registration
│   ├── keyboards.py               # All InlineKeyboardMarkup builders
│   ├── formatter.py               # All message formatters
│   ├── i18n.py                    # Locale strings (en + uk)
│   └── handlers/
│       ├── commands.py            # All slash command handlers
│       ├── message.py             # Plain-text routing: prefix / YouTube / URL / AI router
│       ├── media.py               # Voice / photo / PDF / text file handlers
│       ├── callbacks.py           # InlineKeyboard callback dispatcher
│       ├── youtube_chat.py        # YouTube × NotebookLM session handler
│       └── schedule.py            # Daily / weekly / monthly digest jobs + charts
│
├── git_sync/
│   └── sync.py                    # commit_note() + push_if_due()
│
├── data/
│   └── chroma/                    # ChromaDB vector index (auto-created, gitignored)
│
└── .brain/
    ├── AGENTS.md                  # AI instructions injected into every prompt
    └── skills/
        ├── vault-writer.md        # Folder naming, numbering, MoC rules
        ├── classifier.md          # Classification guidelines
        └── obsidian-rules.md      # Frontmatter schema, tags, wikilink syntax
```

---

## Message routing flow

```
Plain text received
       │
       ├─ Active YouTube session? → handle_question() → NotebookLM Q&A
       │
       ├─ Bare YouTube URL? → start_session() → NotebookLM notebook created
       │
       ├─ Bare URL? → _do_clip() → fetch + AI summarise → save note
       │
       ├─ Pending inline action (move/tags)? → _handle_pending_inline()
       │
       ├─ Group topic thread? → inject [Topic: Name] context prefix
       │
       ├─ Has prefix (задача:/note:/...)? → forced NoteType → save (no AI router)
       │
       └─ AI required?
              │
              ▼
         ⏳ Thinking… (progress message sent)
              │
              ▼
         _route() → ActionPlan (1 AI call)
              │
              ▼
         execute(plan) → dispatcher
              │
    ┌─────────┼──────────────────────────────────┐
    │         │                                  │
CREATE_NOTE  ANSWER_FROM_VAULT           SEARCH_VAULT / CHAT / WEB …
    │         │
format+write  vector search
+duplicate    +AI answer
check         +citations
    │
[📁 Move][🏷️ Tags] inline buttons
(or [🔀 Merge] if duplicate ≥ 85%)
```

---

## Using as a Claude Code MCP server

`vault_writer/server.py` registers as an MCP server. Add to `.claude/mcp_servers.json`:

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

Available MCP tools: `create_note`, `search_notes`, `classify_content`, `update_moc`, `get_vault_index`.

---

## Security

- `config.yaml` is in `.gitignore` — never committed
- `data/chroma/` is in `.gitignore` — vault embeddings never leave the machine
- `api_key` and `bot_token` are never written to logs or AI prompts
- `log_ai_decisions: true` logs only classification metadata — never note content or query text
- All Telegram interactions silently rejected for user IDs not in `allowed_user_ids`
- Path traversal guard in vault writer — notes can only be written inside `vault.path`
- `/settings` toggle persists only boolean flags to `config.yaml` — no arbitrary writes

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `python-telegram-bot >= 20.0` | Async Telegram bot + job scheduler |
| `anthropic` | Claude AI SDK (text + vision) |
| `mcp` | MCP server (stdio transport) |
| `pyyaml` | Read/write `config.yaml` |
| `gitpython` | Git operations on the vault |
| `faster-whisper` | On-device voice transcription |
| `pypdf` | Local PDF text extraction |
| `chromadb` | Embedded vector database |
| `sentence-transformers` | Multilingual text embeddings (offline) |
| `requests` | HTTP calls for Ollama API and web clipping |
| `pytest` | Tests |
| `ffmpeg` (system) | Audio decoding — `winget install ffmpeg` |
| `matplotlib` + `numpy` | Charts for `/stats`, `/graph`, scheduled summaries *(optional)* |
| `networkx` | Knowledge graph generation for `/graph` *(optional)* |
| `notebooklm-py` | YouTube × NotebookLM integration *(optional)* |
