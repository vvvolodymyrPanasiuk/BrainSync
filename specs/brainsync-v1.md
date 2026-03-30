# BrainSync — System Specification v1.0

**Author:** otixDesk
**Date:** 2026-03-30
**Status:** Approved
**Project:** C:\Projects\BrainSync

---

## 1. Title and Metadata

| Field | Value |
|-------|-------|
| Project | BrainSync |
| Version | 1.0 |
| Vault | C:\SecondaryBrain |
| Language | Ukrainian (notes), English (code, instructions) |
| AI Providers | Anthropic Claude (primary), Ollama (future) |

---

## 2. Context

BrainSync is a local personal knowledge management automation system. The user maintains an Obsidian vault (`C:\SecondaryBrain`) as a second brain — a living reference for programming, architecture, business, health, habits, and life in general.

The problem: manually creating well-structured Obsidian notes (with frontmatter, MoC links, wikilinks, tags) is tedious and breaks the flow of capturing ideas. The user wants to capture thoughts from anywhere — primarily Telegram — and have AI handle all structuring, classification, and placement into the vault automatically.

The system must also integrate with Claude Code development sessions, enabling knowledge captured during coding sessions to flow into the vault. A single VaultWriter MCP server serves as the backbone, allowing any source (Telegram, Claude Code, future integrations) to write to the vault through a consistent interface.

---

## 3. Functional Requirements

### 3.1 VaultWriter MCP Server

**FR-1:** The system MUST provide a VaultWriter MCP server that exposes tools for creating, reading, searching, and updating notes in the Obsidian vault.

**FR-2:** VaultWriter MUST expose the following MCP tools:
- `create_note` — create a new note with proper frontmatter, MoC linking, and file placement
- `search_notes` — full-text search across the vault
- `update_moc` — add a note reference to its parent MoC
- `classify_content` — classify raw text into type, topic, and target folder
- `get_vault_index` — return current vault structure (MoCs, notes, tags)

**FR-3:** VaultWriter MUST write `.md` files directly to the vault filesystem without requiring Obsidian to be running.

**FR-4:** VaultWriter MUST use Obsidian CLI for Dataview queries and backlink retrieval when Obsidian is running and `integrations.obsidian_cli.enabled: true`.

**FR-5:** VaultWriter MUST maintain an in-memory vault index, built at startup and updated after every write operation.

**FR-6:** VaultWriter MUST support two AI providers: `anthropic` and `ollama`, switchable via `config.yaml`.

**FR-7:** VaultWriter MUST load `.brain/AGENTS.md` and the relevant skill file from `.brain/skills/` and inject them into every AI prompt.

**FR-8:** VaultWriter MUST inject active config values (language, processing_mode, vault path) into AI prompts at runtime.

### 3.2 AI Classification and Processing

**FR-9:** The system MUST support three processing modes:
- `minimal` — AI classifies only (determines type and target folder). Note saved as-is.
- `balanced` — AI classifies + formats note (frontmatter, sections, structure).
- `full` — AI classifies + formats + enriches (adds wikilinks to existing notes, fills related concepts).

**FR-10:** The system MUST determine content type automatically when no prefix or command is provided, using AI classification.

**FR-11:** The system MUST skip AI classification when the user provides a `/command` or inline `prefix:`, using the explicit type directly.

**FR-12:** Classification MUST return a JSON response with: `type`, `topic`, `folder`, `parent_moc`, `title`, `confidence`.

**FR-13:** In `full` mode, enrichment MUST link to a maximum of `enrichment.max_related_notes` existing vault notes via wikilinks.

**FR-14:** After saving, the system MUST update the parent MoC file by adding the new note to `## 🔑 Main sections` when `enrichment.update_moc: true`.

### 3.3 Telegram Bot

**FR-15:** The Telegram bot MUST only respond to user IDs listed in `telegram.allowed_user_ids`.

**FR-16:** The bot MUST support the following slash commands:
- `/note <text>` — save as note
- `/task <text>` — save as task
- `/idea <text>` — save as idea
- `/journal <text>` — save as journal entry
- `/search <query>` — search vault and return results
- `/mode <minimal|balanced|full>` — switch processing mode for current session
- `/status` — show last saved note, current mode, vault stats
- `/help` — list all commands

**FR-17:** The bot MUST support inline prefixes as alternatives to slash commands:
- `нотатка:`, `note:` → note
- `задача:`, `task:`, `todo:` → task
- `ідея:`, `idea:` → idea
- `день:`, `journal:` → journal

**FR-18:** Plain text without a command or prefix MUST be processed through AI classification.

**FR-19:** After saving, the bot MUST send a confirmation message showing the saved file path.

**FR-20:** The bot MUST support sending `show_ai_reasoning: true` in the confirmation when configured.

### 3.4 Note Structure

**FR-21:** Every created note MUST follow the vault conventions defined in `C:\SecondaryBrain\CLAUDE.md`:
- YAML frontmatter with `title`, `date`, `categories`, `tags`, `MoC`
- Tags in plural form (`#areas/backend`, `#types/notes`)
- Wikilinks to related notes
- Sections: Description, Conclusions, Links

**FR-22:** MoC notes MUST follow the MoC template with sections: Description, Main sections, Related MoC/Links, Additional resources, Conclusions.

**FR-23:** Note filenames MUST follow conventions:
- Regular notes: `NNNN Title.md` (numbered sequentially within folder)
- MoC files: `0 TopicName.md`
- Detailed articles: placed in `_data/` subfolder

### 3.5 Git Sync

**FR-24:** When `git.enabled: true`, the system MUST commit changes to git after every save operation.

**FR-25:** When `git.push_remote: true`, the system MUST push to the configured remote on the configured interval (`git.push_interval_minutes`).

**FR-26:** Commit messages MUST use the template: `vault: auto-save {date} {time}`.

### 3.6 Scheduled Summaries

**FR-27:** When `schedule.daily_summary.enabled: true`, the bot MUST send a daily summary at the configured time containing: notes added today, tasks created, and pending tasks.

**FR-28:** When `schedule.weekly_review.enabled: true`, the bot MUST send a weekly summary on the configured day containing: notes added this week, progress on goals from `Плани на 2026.md`, and a count by topic.

**FR-29:** When `schedule.monthly_review.enabled: true`, the bot MUST send a monthly summary on the configured day containing: total notes added, new topics, and vault growth statistics.

### 3.7 Claude Code Integration

**FR-30:** VaultWriter MUST be registerable as an MCP server in `.claude/mcp_servers.json` in any project directory.

**FR-31:** When `claude_code.enabled: true` and `capture_trigger: manual`, the system MUST save to vault only when explicitly called via `create_note` MCP tool or `/save` command.

**FR-32:** When `claude_code.save_raw: true`, session content MUST be saved without AI summarization.

**FR-33:** When `claude_code.max_session_tokens` is exceeded, the system MUST skip saving and notify the user.

### 3.8 Setup Installer

**FR-34:** The system MUST provide a `setup.py` installer that runs interactively in the terminal and:
1. Asks for vault path, Telegram bot token, Telegram user ID, AI provider, API key, processing mode, git sync preference, and git remote URL
2. Generates `config.yaml` from answers
3. Creates `.brain/AGENTS.md` and `skills/` from templates
4. Indexes the vault
5. Tests connections (Telegram API, AI provider, git remote)
6. Starts the bot

**FR-35:** Setup MUST display a success message with bot status and instructions after completion.

---

## 4. Non-Functional Requirements

**NFR-1:** The VaultWriter server MUST start within 10 seconds on a standard PC.

**NFR-2:** Vault indexing at startup MUST complete within 5 seconds for up to 500 notes.

**NFR-3:** A single note save (minimal mode) MUST complete within 3 seconds end-to-end (Telegram message → confirmation reply).

**NFR-4:** The system MUST run entirely locally. No data MUST be sent to third parties except the configured AI provider API.

**NFR-5:** Only Telegram user IDs in `telegram.allowed_user_ids` MUST be able to interact with the bot.

**NFR-6:** API keys MUST be stored only in `config.yaml` and MUST NOT be logged.

**NFR-7:** The system MUST be runnable on Windows 11 with Python 3.12+.

**NFR-8:** All AI provider calls MUST be abstracted behind a single `AIProvider` interface to allow switching providers without code changes.

---

## 5. Acceptance Criteria

**AC-1 (FR-1, FR-2):** Given VaultWriter is started, when a Claude Code session connects via MCP, then all 5 tools (`create_note`, `search_notes`, `update_moc`, `classify_content`, `get_vault_index`) are available.

**AC-2 (FR-10, FR-12):** Given processing_mode is `balanced`, when the user sends "дізнався що CQRS розділяє read і write моделі" without a prefix, then the system calls AI classification and returns JSON with `type: note`, `folder` containing `Architecture`, and `confidence >= 0.7`.

**AC-3 (FR-11):** Given the user sends `/task купити молоко`, then classification AI is NOT called, type is set to `task`, and 0 AI API calls are made.

**AC-4 (FR-14, FR-21):** Given a new note is created in `Architecture/`, when the note is saved, then `0 Architecture.md` contains a new wikilink to the note in `## 🔑 Main sections`.

**AC-5 (FR-15):** Given an unknown Telegram user sends a message, then the bot does NOT respond and logs the attempt.

**AC-6 (FR-16):** Given the user sends `/search Redis`, then the bot replies with a list of matching notes including file paths.

**AC-7 (FR-19):** Given a note is saved successfully, then the bot replies with a message containing the saved file path, e.g., `✓ Збережено → Architecture/0004 CQRS патерн.md`.

**AC-8 (FR-24, FR-26):** Given `git.enabled: true`, when a note is saved, then a git commit is created with message matching `vault: auto-save YYYY-MM-DD HH:MM`.

**AC-9 (FR-34):** Given the user runs `python setup.py`, when they answer all prompts, then `config.yaml` is created, vault is indexed, and the bot starts successfully.

**AC-10 (FR-6, NFR-8):** Given `ai.provider: ollama` in config, when a note is classified, then the system calls the Ollama API at `ai.ollama_url` instead of Anthropic.

**AC-11 (FR-9):** Given `processing_mode: minimal`, when a note is saved, then at most 1 AI API call is made (classification only), and no enrichment or MoC update via AI occurs.

**AC-12 (FR-27):** Given `schedule.daily_summary.enabled: true` and time is reached, then the bot sends a Telegram message listing notes added today and pending tasks.

---

## 6. Edge Cases

**EC-1:** If the vault path in `config.yaml` does not exist, setup MUST fail with a clear error message and not start the bot.

**EC-2:** If the AI provider API call fails (timeout, rate limit, network error), the system MUST save the note in `minimal` mode as fallback and notify the user.

**EC-3:** If a new note's target folder does not exist, VaultWriter MUST create the folder before writing the file.

**EC-4:** If the parent MoC file does not exist for a new topic, VaultWriter MUST create a new MoC file from `Template-MoC.md` before adding the link.

**EC-5:** If `max_session_tokens` is exceeded in Claude Code integration, the system MUST skip saving and send a Telegram notification (if bot is running).

**EC-6:** If the git remote is unreachable during push, the system MUST continue operating normally and retry on the next interval.

**EC-7:** If two notes are created with the same numbered filename (race condition), the second MUST increment the number until unique.

**EC-8:** If Obsidian CLI is enabled but Obsidian is not running, the system MUST fall back to direct file operations without error.

**EC-9:** If `telegram.allowed_user_ids` is empty list, the bot MUST refuse all messages and log a warning at startup.

---

## 7. API Contracts

### MCP Tools

```typescript
// create_note
interface CreateNoteInput {
  text: string;                          // raw input text
  type?: "note" | "task" | "idea" | "journal";  // optional override
  folder?: string;                       // optional folder override
}
interface CreateNoteOutput {
  success: boolean;
  file_path: string;                     // relative to vault root
  title: string;
  parent_moc: string;
  ai_calls_made: number;
}

// search_notes
interface SearchNotesInput {
  query: string;
  limit?: number;                        // default: 10
  folder?: string;                       // optional scope
}
interface SearchNotesOutput {
  results: Array<{
    file_path: string;
    title: string;
    excerpt: string;
    score: number;
  }>;
}

// classify_content
interface ClassifyContentInput {
  text: string;
}
interface ClassifyContentOutput {
  type: "note" | "task" | "idea" | "journal";
  topic: string;
  folder: string;
  parent_moc: string;
  title: string;
  confidence: number;                    // 0.0 - 1.0
}

// update_moc
interface UpdateMocInput {
  moc_path: string;                      // relative to vault
  note_path: string;                     // relative to vault
  note_title: string;
}
interface UpdateMocOutput {
  success: boolean;
}

// get_vault_index
interface GetVaultIndexOutput {
  total_notes: number;
  mocs: Array<{ path: string; title: string; children: string[] }>;
  topics: string[];
  last_updated: string;                  // ISO datetime
}
```

### AI Provider Interface

```python
class AIProvider:
    def complete(self, prompt: str, max_tokens: int = 1000) -> str: ...

class AnthropicProvider(AIProvider): ...
class OllamaProvider(AIProvider): ...
```

---

## 8. Data Models

### config.yaml

```yaml
ai:
  provider: string          # "anthropic" | "ollama"
  model: string
  ollama_url: string        # default: "http://localhost:11434"
  processing_mode: string   # "minimal" | "balanced" | "full"

vault:
  path: string
  language: string          # "uk"

enrichment:
  add_wikilinks: boolean
  update_moc: boolean
  max_related_notes: integer
  scan_vault_on_start: boolean

telegram:
  bot_token: string
  allowed_user_ids: list[integer]

prefixes:
  note: list[string]
  task: list[string]
  idea: list[string]
  journal: list[string]

git:
  enabled: boolean
  auto_commit: boolean
  commit_message: string
  push_remote: boolean
  remote: string
  branch: string
  push_interval_minutes: integer

schedule:
  daily_summary:
    enabled: boolean
    time: string            # "HH:MM"
  weekly_review:
    enabled: boolean
    day: string             # "monday" .. "sunday"
    time: string
  monthly_review:
    enabled: boolean
    day: integer            # 1-28
    time: string

claude_code:
  enabled: boolean
  capture_trigger: string   # "manual" | "auto"
  save_raw: boolean
  max_session_tokens: integer
  allowed_projects: list[string]

integrations:
  obsidian_cli:
    enabled: boolean
  notebooklm:
    enabled: boolean

logging:
  level: string             # "debug" | "info" | "warn" | "error"
  log_to_file: boolean
  log_path: string
  log_ai_decisions: boolean
```

### VaultNote

```python
@dataclass
class VaultNote:
    title: str
    date: str               # YYYY-MM-DD
    categories: list[str]
    tags: list[str]
    moc: str                # wikilink to parent MoC
    content: str            # markdown body
    file_path: str          # relative to vault root
    note_type: str          # "note" | "task" | "idea" | "journal"
```

---

## 9. Out of Scope (v1.0)

**OS-1:** NotebookLM integration — excluded from v1, placeholder in `integrations/` only.

**OS-2:** Notion sync — excluded from v1.

**OS-3:** Ollama provider implementation — config and interface defined, implementation deferred to v1.1.

**OS-4:** `/open` command (open note in Obsidian via CLI) — deferred to v1.1.

**OS-5:** Auto-capture of full Claude Code sessions (`capture_trigger: auto`) — deferred, only `manual` in v1.

**OS-6:** Web UI — no web interface in any version planned currently.

**OS-7:** Multi-user support — single user only, enforced via `allowed_user_ids`.

**OS-8:** Voice messages in Telegram — text only in v1.

---

## 10. Implementation Phases

### Phase 1 — Core (MVP)
- VaultWriter MCP Server (FR-1 to FR-8)
- vault/reader.py, writer.py, indexer.py
- ai/classifier.py, formatter.py
- config.yaml + .brain/AGENTS.md + .brain/skills/
- Telegram bot with commands (FR-15 to FR-20)
- Git sync (FR-24 to FR-26)
- setup.py installer (FR-34, FR-35)

### Phase 2 — Enrichment + Search
- ai/enricher.py (FR-13, FR-14)
- search_notes tool (FR-2)
- Obsidian CLI integration (FR-4)
- Vault index auto-generation

### Phase 3 — Claude Code Integration
- MCP server registration docs
- claude_code config (FR-30 to FR-33)
- Session note template

### Phase 4 — Scheduled Summaries
- schedule handlers (FR-27 to FR-29)
- Summary generation prompts

### Phase 5 — Extensions
- Ollama provider (OS-3 lifted)
- NotebookLM integration (OS-1 lifted)
- /open command (OS-4 lifted)
