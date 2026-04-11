# BrainSync Development Guidelines

Last updated: 2026-04-09

## IMPORTANT: README must always be up to date

**After every change to the project — new feature, new command, config change, dependency added, architecture change — update `README.md` to reflect the current state.**

Specifically update:
- Feature list (new capabilities)
- Bot commands table (new or removed commands)
- Configuration reference (new config keys)
- Project structure (new files/modules)
- Dependencies table (new packages)
- Message routing flow (if routing logic changed)

Do NOT leave README describing old behaviour after code changes.

---

## REQUIRED: Claude Code CLI

**Claude Code CLI is a mandatory runtime dependency of BrainSync.**

The bot uses `provider: claude_code` in `config.yaml`, which spawns `claude -p <prompt>`
as a subprocess for every AI call. This gives the bot full Claude Code capabilities:
web search, file reading, MCP tools, bash execution.

Install Claude Code before running the bot:
- Download: https://claude.ai/download
- Verify: `claude --version`

**Ollama backend** (recommended for local use):
```bash
# 1. Install Ollama: https://ollama.com
ollama pull kimi-k2.5:cloud
# 2. Set in config.yaml:
#    provider: claude_code
#    model: kimi-k2.5:cloud
#    claude_code_use_ollama: true
```

**Native Anthropic** (cloud):
```bash
# Set ANTHROPIC_API_KEY env var, then in config.yaml:
#    provider: claude_code
#    model: claude-sonnet-4-6
#    claude_code_use_ollama: false
```

---

## Active Technologies

- **Python 3.12+** on Windows 11
- **Claude Code CLI** — mandatory AI runtime (`claude` must be in PATH)
- **python-telegram-bot v20+** (async PTB, job queue)
- **ChromaDB** embedded (`data/chroma/`) — local, no server, gitignored
- **sentence-transformers** + torch (CPU) for embeddings
- **faster-whisper** for on-device voice transcription
- **Ollama** (optional Ollama backend for Claude Code) or **Anthropic Claude** (cloud backend)
- **uv** — package manager (replaces pip + venv)
- **notebooklm-py** — optional, YouTube × NotebookLM integration
- **matplotlib + numpy** — optional, for charts in `/stats` and scheduled summaries

---

## Project Structure

```
BrainSync/
├── main.py                  # Entry point
├── setup.py                 # Interactive config wizard
├── config/loader.py         # AppConfig dataclasses + validation
├── vault_writer/
│   ├── ai/router.py         # AI Semantic Router → ActionPlan
│   ├── ai/classifier.py     # Legacy classification path
│   ├── tools/executor.py    # ActionPlan dispatcher
│   ├── tools/health.py
│   ├── tools/web_clip.py
│   ├── rag/                 # BM25 + ChromaDB embeddings + hybrid search + RAG engine
│   └── vault/               # writer, indexer, structure
├── telegram/
│   ├── bot.py               # All handler registration
│   ├── keyboards.py         # InlineKeyboardMarkup builders
│   ├── i18n.py              # Locale strings (en + uk)
│   └── handlers/
│       ├── commands.py      # Slash command handlers
│       ├── message.py       # Plain-text routing
│       ├── callbacks.py     # Inline button callbacks
│       ├── youtube_chat.py  # YouTube × NotebookLM
│       ├── media.py         # Voice/photo/PDF/file
│       └── schedule.py      # Scheduled jobs + PNG charts
└── git_sync/sync.py
```

---

## Commands

```bash
cd C:/Projects/BrainSync
py -m pytest
ruff check .
py -m py_compile <file>    # quick syntax check before committing
```

---

## Code Style

- Python 3.12+ on Windows 11
- Follow standard Python conventions (PEP 8)
- All new Telegram handlers must check `auth_check(update, config)` first
- All new handlers must be registered in `telegram/bot.py`
- New i18n strings go into **both** `"en"` and `"uk"` dicts in `telegram/i18n.py`
- Graceful fallbacks for optional dependencies (matplotlib, networkx, notebooklm-py) — catch `ImportError` and show an install hint
- `execute()` in `executor.py` returns `tuple[str, InlineKeyboardMarkup | None]` — all callers must unpack the tuple

---

## Architecture Notes

- **AI Semantic Router** (`vault_writer/ai/router.py`): single AI call per message → `ActionPlan` dataclass with intent, folder (4-level hierarchy), note_type, tags, title, should_save, etc.
- **Executor** (`vault_writer/tools/executor.py`): dispatches on `ActionPlan.intent`, returns `(reply_text, keyboard | None)`
- **Inline keyboards** (`telegram/keyboards.py`): all `InlineKeyboardMarkup` builders live here
- **Callback router** (`telegram/handlers/callbacks.py`): dispatches on `query.data` prefix
- **Hybrid search** (`vault_writer/rag/`): BM25 (`bm25_index.py`) + ChromaDB vectors merged via RRF in `vector_store.hybrid_search()`; used by RAG, Telegram search, and MCP `search_notes`
- **MCP server** (`vault_writer/server.py`): tools: `create_note`, `search_notes`, `classify_content`, `update_moc`, `get_vault_index`, `save_conversation`
- **Settings persistence**: `callbacks.py::_persist_setting()` writes back to `config.yaml` via `yaml.dump`
- **Charts**: always use `matplotlib.use("Agg")` (no display), wrap in try/except ImportError

---

## Key config keys added recently

```yaml
schedule:
  stale_task_reminder:
    enabled: false
    days: 7
    time: "09:00"

embedding:
  similarity_duplicate_threshold: 0.85
  similarity_related_threshold: 0.70
```

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
