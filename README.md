# 🧠 BrainSync

**Local AI-powered personal knowledge management via Telegram.**

Send a message, voice note, photo, or PDF → AI classifies, formats, and saves it as a structured Markdown note in your Obsidian vault. Ask questions about your notes in natural language — the bot searches your vault semantically and answers using only your own knowledge. Everything runs locally, nothing leaves your machine except optional AI API calls.

---

## What it does

BrainSync solves two problems: **capture** and **retrieval**.

**Capture** — you have a thought while doing something else. You open Telegram (which you already have open), send a message, and it appears in your vault as a properly formatted note — correct folder, frontmatter, wikilinks to related notes, added to the Map of Content. Zero manual filing.

**Retrieval** — you remember writing something about a topic but can't find it. Instead of searching Obsidian with keywords, you ask the bot in plain language: *"що я думав про CQRS?"* — it finds semantically relevant notes and gives you a synthesized answer with citations, even if your notes never contained the exact words you typed.

---

## Features

### Capture

| What you send | What happens |
|---------------|--------------|
| Plain text message | AI classifies → formats → saves as note |
| Text with inline prefix (`task:`, `ідея:`) | Forced type, skips classification |
| Voice message | On-device transcription (Whisper) → note |
| Photo | AI visual description → note |
| PDF file | Full text extracted locally → note |
| `.txt` / `.md` file | Content saved directly as note |

### Intelligence

- **Intent detection** — every plain-text message is automatically classified as a question about the vault, a search request, or a new note. No slash commands needed.
- **Semantic search** — `/search` and natural language search queries use vector embeddings; finds notes by meaning, not exact words. Works in Ukrainian.
- **RAG answers** — questions about your vault get synthesized answers grounded exclusively in your own notes, with source citations.
- **Duplicate detection** — after every note save, the bot checks for semantically similar existing notes (≥ 70% similarity) and warns you.
- **Three AI processing modes** — `minimal` (fast, 0–1 calls), `balanced` (classify + format), `full` (+ automatic wikilinks to related notes).

### Automation

- **Map of Content** — index files auto-updated every time a note is added to a topic
- **Git sync** — vault auto-committed and pushed after every note (configurable interval)
- **Scheduled digests** — daily, weekly, and monthly summaries sent to Telegram
- **MCP server** — exposes vault operations to Claude Code sessions

### Infrastructure

- **Fully offline capable** — sentence-transformers backend for embeddings, Ollama for AI, Whisper for voice; no external API calls required
- **Vector index persists** — ChromaDB stores embeddings locally in `data/chroma/`; index survives restarts
- **Background indexing** — vault is indexed at startup without blocking the bot

---

## Prerequisites

Before running BrainSync, make sure you have:

1. **Python 3.12+** — [python.org/downloads](https://python.org/downloads). During installation on Windows, check "Add Python to PATH".

2. **Git** — [git-scm.com](https://git-scm.com). Required for vault auto-commit and for cloning the repo.

3. **ffmpeg** — required for voice message decoding.
   ```
   winget install ffmpeg        # Windows
   brew install ffmpeg          # macOS
   sudo apt install ffmpeg      # Ubuntu/Debian
   ```

4. **An Obsidian vault** — an existing folder where your `.md` notes live. Example: `C:\SecondaryBrain`. The Obsidian app does not need to be running.

5. **A Telegram bot** — create one via [@BotFather](https://t.me/BotFather) and copy the token.

6. **Your Telegram user ID** — get it from [@userinfobot](https://t.me/userinfobot).

7. **AI provider** — either:
   - [Anthropic API key](https://console.anthropic.com) (cloud, requires internet)
   - [Ollama](https://ollama.com) running locally (fully offline, free)

---

## Installation

### Option A: One-click (Windows)

```bash
git clone https://github.com/vvvolodymyrPanasiuk/BrainSync.git
cd BrainSync
```

Double-click **`start.bat`**.

The script will:
1. Check that Python 3.12+ is available
2. Install [`uv`](https://github.com/astral-sh/uv) (fast package manager) if needed
3. Install all dependencies into an isolated virtual environment
4. Launch the interactive setup wizard on first run

On every subsequent run, if `config.yaml` already exists, setup is skipped and the bot starts immediately.

### Option B: Manual

```bash
# 1. Clone
git clone https://github.com/vvvolodymyrPanasiuk/BrainSync.git
cd BrainSync

# 2. Install uv (replaces pip + venv)
pip install uv

# 3. Install dependencies (creates .venv automatically)
uv sync

# 4. Run the interactive setup wizard
uv run python setup.py

# 5. Start the bot
uv run python main.py
```

### New dependencies for semantic search

If you cloned before the semantic search feature was added, install the new packages:

```bash
pip install chromadb sentence-transformers
```

> The `sentence-transformers` model (~120 MB) downloads automatically on first start.
> ChromaDB stores the vector index locally in `data/chroma/` — it's gitignored.

---

## First run

When you run `setup.py`, it will ask:

| Question | Example answer |
|----------|---------------|
| Vault path | `C:\SecondaryBrain` |
| AI provider | `anthropic` or `ollama` |
| API key (if Anthropic) | `sk-ant-...` |
| Telegram bot token | `7123456789:AAF...` |
| Your Telegram user ID | `123456789` |

The wizard creates `config.yaml` in the project root. That file is gitignored — it will never be committed.

---

## Starting the bot

```bash
# Windows (recommended)
start.bat

# macOS / Linux
bash start.sh

# Direct
uv run python main.py
```

On first start you'll see:

```
INFO  BrainSync starting — mode=balanced provider=anthropic
INFO  Vault index built: 47 notes, 8 topics
INFO  VectorStore initialised at data/chroma
INFO  Background vault indexing started
INFO  Telegram bot starting...
```

The bot sends you a Telegram message when the Whisper model finishes loading and it's ready to accept messages. While the vector index is being built in the background, the bot is fully responsive — queries during indexing use a partial index and show a soft notice.

Press `Ctrl+C` to stop.

---

## Bot commands

| Command | Description |
|---------|-------------|
| `/note <text>` | Save a note |
| `/task <text>` | Save a task |
| `/idea <text>` | Save an idea |
| `/journal <text>` | Save a journal entry |
| `/search <query>` | Semantic vault search |
| `/reindex` | Rebuild the vector index from all vault notes |
| `/mode minimal\|balanced\|full` | Change processing mode |
| `/status` | Show bot status and session stats |
| `/help` | List all commands |

---

## Inline prefixes

You don't need a slash command. Add a prefix at the start of any message (or as a media caption):

```
note: ...       нотатка: ...
task: ...       задача: ...     todo: ...
idea: ...       ідея: ...
journal: ...    день: ...
```

Prefix matching is case-insensitive and works on voice captions, photo captions, and file captions.

Any plain message **without** a prefix or slash command is routed through intent detection (see below).

---

## Sending media

### Voice messages

Hold the mic button in Telegram and send a voice message. BrainSync:
1. Downloads the `.ogg` file
2. Transcribes it on-device via Whisper (Ukrainian supported)
3. Saves the transcription as a note

Add a caption to force a type: `задача:` as a voice caption saves the transcription as a task.

**Limits:** configurable via `media.max_voice_duration_seconds` (default 300s).

**Model download:** on first start, the Whisper `small` model (~466 MB) downloads automatically. The bot sends you a Telegram notification. After that, model loads from local cache instantly.

### Photos

Send any photo. BrainSync:
1. Downloads the image
2. Sends it to the AI for visual description
3. Saves the description as a note

Requires `ollama_vision_model` set (e.g. `llava`) if using Ollama, or any Claude model if using Anthropic. If the provider doesn't support vision, the bot saves the caption only and warns you.

### PDFs

Attach any PDF file. BrainSync:
1. Extracts the full text locally using `pypdf` (no internet)
2. Sends the first 3 000 characters to AI for classification and title generation
3. Saves the **full** extracted text to the vault

**Limits:** configurable via `media.pdf_max_pages` (default 50) and `media.max_file_size_mb` (default 20).

### Plain text / Markdown files

Attach a `.txt` or `.md` file. The content is saved as a note directly.

---

## Natural language vault interaction

This is the intelligence layer. Every plain-text message without a prefix goes through intent detection before being processed.

### How intent detection works

The bot makes one AI call to classify your message into one of three intents:

| Intent | Trigger examples | What happens |
|--------|-----------------|--------------|
| `rag_query` | "що я думав про CQRS?", "як я вирішував проблему кешування?" | Vault search + AI synthesizes answer |
| `search_query` | "знайди нотатки про архітектуру", "є щось про Redis?" | Vault search → ranked result list |
| `new_note` | "CQRS розділяє read і write" (statement, not question) | Classified and saved as a note |

If the AI provider is unavailable or the vector index isn't built yet, the bot falls back to saving everything as a note (safe default).

### Asking questions about your vault (RAG)

```
You: що я думав про CQRS?

Bot: 💡 На основі твого vault:

     CQRS розділяє команди (write) і запити (read) у різні моделі.
     Я писав, що це найкраще застосовувати коли read і write
     мають різні вимоги до продуктивності.

     Джерела:
     → Architecture/0004 CQRS pattern.md
     → Architecture/0007 Event Sourcing.md
```

The answer is synthesized **only from your notes** — the AI is explicitly instructed not to use general knowledge. If nothing relevant is found:

```
Bot: 🔍 Нічого не знайдено у vault за цим запитом.
```

### Semantic search

```
You: знайди нотатки про управління часом

Bot: 🔍 Знайдено 3 нотатки для "управління часом":

     1. Productivity/0008 deep work notes.md (89%)
        ...deep work — стан потоку без відволікань...

     2. Productivity/0012 morning routine.md (74%)
        ...ранковий ритуал допомагає структурувати день...

     3. General/0003 book summary.md (71%)
        ...четверта година дня найбільш продуктивна...
```

Works even when the exact words don't appear in any note — search is by semantic meaning, not keywords.

Same results for `/search управління часом`.

### Duplicate detection

After every note save, BrainSync checks for semantically similar existing notes:

```
You: CQRS is a pattern where read and write models are separated

Bot: ✓ Saved → Architecture/0011 CQRS notes.md

     ⚠️ Схожа нотатка вже існує:
     → Architecture/0004 CQRS pattern.md (91%)
```

Or for related (not duplicate) notes:

```
Bot: ✓ Saved → Productivity/0015 focus tips.md

     💡 Можливо пов'язана нотатка:
     → Productivity/0008 deep work notes.md (74%)
```

Thresholds: ≥ 85% = duplicate warning, 70–84% = related suggestion. Configurable in `config.yaml`.

### Rebuilding the index

If you added notes directly in Obsidian (outside the bot), run `/reindex`:

```
You: /reindex

Bot: ⏳ Переіндексація vault…
Bot: ✅ Переіндексовано: 63 нотатки.
```

---

## Configuration reference

`config.yaml` is generated by `setup.py` and is never committed. Add the `embedding:` block manually if you're upgrading from an older version.

### AI settings

```yaml
ai:
  provider: "anthropic"           # "anthropic" | "ollama"
  model: "claude-sonnet-4-6"      # Used for all AI calls (classification, formatting, RAG)
  ollama_url: "http://localhost:11434"
  ollama_vision_model: ""         # Ollama vision model for photos — e.g. "llava"
  processing_mode: "balanced"     # "minimal" | "balanced" | "full"
  agents_file: ".brain/AGENTS.md"
  skills_path: ".brain/skills/"
  inject_vault_index: true        # Pass known topics to AI during classification
  max_context_tokens: 4000
  api_key: ""                     # Never logged, never committed
```

**Processing modes:**

| Mode | AI calls | What happens |
|------|----------|--------------|
| `minimal` | 0–1 | Classification only (skipped if prefix used) |
| `balanced` | 1–2 | Classification + content formatting |
| `full` | 2–3 | Classification + formatting + auto wikilinks |

Change at runtime with `/mode balanced`. Takes effect after restart.

### Vault settings

```yaml
vault:
  path: "C:\\SecondaryBrain"
  language: "uk"                  # Language hint for AI prompts
```

### Embedding / semantic search settings

```yaml
embedding:
  backend: "sentence-transformers"          # "sentence-transformers" | "ollama"
  model: "paraphrase-multilingual-MiniLM-L12-v2"  # Multilingual, works with Ukrainian
  ollama_embed_url: "http://localhost:11434"       # Only used if backend = "ollama"
  index_path: "data/chroma"                        # Where ChromaDB stores vectors
  similarity_duplicate_threshold: 0.85             # ≥ this → "Схожа нотатка" warning
  similarity_related_threshold: 0.70               # ≥ this → "Пов'язана нотатка" notice
  top_k_results: 5                                 # Max results for search/RAG
```

**Ollama embedding backend** — if you prefer to use Ollama for embeddings:

```bash
ollama pull nomic-embed-text
```

Then change `backend: "ollama"` and `model: "nomic-embed-text"` in `config.yaml`, and run `/reindex`.

### Media settings

```yaml
media:
  max_voice_duration_seconds: 300
  transcription_model: "small"    # Whisper sizes: tiny / base / small / medium / large-v3
  pdf_max_pages: 50
  pdf_ai_context_chars: 3000
  max_file_size_mb: 20
```

Whisper model sizes and trade-offs:

| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| `tiny` | ~75 MB | Fast | Low |
| `base` | ~145 MB | Fast | OK |
| `small` | ~466 MB | Medium | Good (recommended) |
| `medium` | ~1.5 GB | Slow | Very good |
| `large-v3` | ~3 GB | Very slow | Best |

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
  allowed_user_ids: [123456789]   # Only these IDs can interact with the bot
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
    time: "21:00"
  weekly_review:
    enabled: true
    day: "sunday"
    time: "20:00"
  monthly_review:
    enabled: true
    day: 1
    time: "10:00"
```

- **Daily** — today's notes + all open tasks (`- [ ] ...`) across task-type notes
- **Weekly** — note count by topic for the past 7 days
- **Monthly** — notes added this month + new topics introduced

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
  log_to_file: true
  log_path: "logs/vault.log"
  log_ai_decisions: true          # Logs type + folder + confidence only, never note content
```

---

## Note format

Every note created by BrainSync follows this structure:

```markdown
---
title: "CQRS Pattern"
date: 2026-03-30
categories: [Architecture]
tags: [areas/architecture, types/notes]
MoC: "[[0 Architecture]]"
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
**MoC files:** `0 TopicName.md` — always at the root of their folder, excluded from note numbering and vector indexing.

---

## Running fully offline

BrainSync can run without any internet connection or paid API:

1. Install and start [Ollama](https://ollama.com)
2. Pull models:
   ```bash
   ollama pull mistral              # or any other text model
   ollama pull llava                # for photo descriptions
   ollama pull nomic-embed-text     # for embeddings (alternative to sentence-transformers)
   ```
3. In `config.yaml`:
   ```yaml
   ai:
     provider: "ollama"
     model: "mistral"
     ollama_vision_model: "llava"
   embedding:
     backend: "sentence-transformers"   # works offline without Ollama
     # or: backend: "ollama"
     # model: "nomic-embed-text"
   ```
4. Start BrainSync normally

Whisper voice transcription is always offline regardless of AI provider.

---

## Project structure

```
BrainSync/
│
├── main.py                        # Entry point — starts the Telegram bot
├── setup.py                       # Interactive installer
├── start.bat / start.sh           # Launch scripts (detect Python, install uv, start)
├── config.yaml                    # Generated by setup.py — gitignored
│
├── config/
│   └── loader.py                  # Parses config.yaml → AppConfig dataclasses
│                                  # EmbeddingConfig, MediaConfig, factory functions
│
├── vault_writer/                  # Core library — shared by both processes
│   ├── server.py                  # MCP server (standalone process, stdio transport)
│   │
│   ├── ai/
│   │   ├── provider.py            # AIProvider ABC + ProcessingMode enum
│   │   ├── anthropic_provider.py  # Claude text + vision
│   │   ├── ollama_provider.py     # Ollama text + vision
│   │   ├── transcriber.py         # Whisper on-device voice transcription
│   │   ├── classifier.py          # classify() → ClassificationResult
│   │   ├── formatter.py           # format_note() → structured markdown
│   │   └── enricher.py            # add_wikilinks() (full mode only)
│   │
│   ├── media/
│   │   └── pdf_extractor.py       # Local PDF text extraction via pypdf
│   │
│   ├── rag/
│   │   ├── embedder.py            # EmbeddingProvider ABC + SentenceTransformers + Ollama
│   │   ├── vector_store.py        # ChromaDB wrapper (upsert, search, find_similar, reindex)
│   │   ├── intent.py              # classify_intent() → IntentType (rag/search/note)
│   │   └── engine.py              # answer_query(), search_vault(), RAGResult, SearchResult
│   │
│   ├── vault/
│   │   ├── writer.py              # write_note(), update_moc(), sequential numbering
│   │   ├── reader.py              # read_frontmatter(), read_note_content()
│   │   └── indexer.py             # build_index(), update_index() → VaultIndex
│   │
│   └── tools/                     # MCP tool handlers
│       ├── create_note.py         # Orchestrator: classify→format→enrich→write→MoC→upsert
│       ├── search_notes.py        # Keyword full-text search (zero AI calls)
│       ├── classify_content.py    # Text classification
│       ├── update_moc.py          # Map of Content updater
│       └── get_vault_index.py     # Vault index snapshot
│
├── telegram/
│   ├── bot.py                     # PTB Application setup, handler registration
│   ├── formatter.py               # All message formatters (RAG, search, similarity, etc.)
│   └── handlers/
│       ├── commands.py            # All slash command handlers (+ /reindex)
│       ├── message.py             # Intent routing: RAG / search / new note
│       ├── media.py               # Voice / photo / PDF / text file handlers
│       └── schedule.py            # Daily / weekly / monthly digest jobs
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
        ├── classifier.md          # Classification guidelines + JSON output format
        └── obsidian-rules.md      # Frontmatter schema, tags, wikilink syntax
```

---

## Message routing flow

How a plain-text message gets processed end-to-end:

```
Plain text received
       │
       ▼
  auth_check()          Reject if user_id not in allowed_user_ids
       │
       ▼
  detect_prefix()       "task: ..." → forced NoteType, skip classification
       │
  [no prefix]
       │
       ▼
  classify_intent()     1 AI call → rag_query / search_query / new_note
       │
  ┌────┴─────────────────────────┐
  │                              │                       │
rag_query               search_query                new_note
  │                              │                       │
answer_query()          search_vault()          classify() → format_note()
  │                              │              write_note() → update_moc()
RAGResult               list[SearchResult]      upsert_note() → find_similar()
  │                              │                       │
reply with              reply ranked            reply confirmation
answer + citations      results + scores        + similarity notices
```

---

## Using as a Claude Code MCP server

`vault_writer/server.py` registers as an MCP server in Claude Code sessions. Add to your project's `.claude/mcp_servers.json`:

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

Available MCP tools:

| Tool | Description |
|------|-------------|
| `create_note` | Full pipeline: classify → format → write → update MoC → index |
| `search_notes` | Keyword full-text search |
| `classify_content` | Return type, folder, and title for any text |
| `update_moc` | Manually update a Map of Content file |
| `get_vault_index` | Get a snapshot of all known topics and note counts |

---

## Security

- `config.yaml` is in `.gitignore` — never committed
- `data/chroma/` is in `.gitignore` — your personal vault embeddings never leave the machine
- `api_key` and `bot_token` are never written to logs, console, or AI prompts
- `log_ai_decisions: true` logs only classification metadata (type + folder + confidence) — never note content, never query text
- The bot silently rejects every user ID not in `allowed_user_ids`
- Path traversal guard in vault writer — notes can only be written inside `vault.path`

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
| `chromadb` | Embedded vector database (local, no server) |
| `sentence-transformers` | Multilingual text embeddings (offline capable) |
| `requests` | HTTP calls for Ollama API |
| `pytest` | Tests |
| `ffmpeg` (system) | Audio decoding for voice — `winget install ffmpeg` |
