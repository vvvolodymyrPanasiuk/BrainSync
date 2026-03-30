---
description: "Task list for BrainSync MVP implementation"
---

# Tasks: BrainSync — Personal Knowledge Automation System

**Input**: `specs/001-brainsync-mvp/plan.md`, `spec.md`, `data-model.md`, `contracts/`
**Branch**: `001-brainsync-mvp`

**Organization**: Tasks grouped by User Story for independent implementation and testing.
**Tests**: Not requested — test tasks omitted unless noted.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to

---

## Phase 1: Setup

**Purpose**: Project initialization and shared infrastructure scaffolding.

- [x] T001 Create project directory structure per plan.md: `vault_writer/`, `telegram/`, `git_sync/`, `config/`, `tests/`, `.brain/`
- [x] T002 [P] Create `requirements.txt` with: `python-telegram-bot>=20.0`, `anthropic`, `mcp`, `pyyaml`, `gitpython`, `pytest`
- [x] T003 [P] Create `.gitignore` including: `config.yaml`, `.venv/`, `logs/`, `__pycache__/`, `*.pyc`
- [x] T004 [P] Create empty `__init__.py` files in all packages: `vault_writer/`, `vault_writer/tools/`, `vault_writer/ai/`, `vault_writer/vault/`, `telegram/`, `telegram/handlers/`, `git_sync/`, `config/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that ALL user stories depend on.

⚠️ **CRITICAL**: No user story work can begin until this phase is complete.

- [x] T005 Implement `AppConfig` dataclass hierarchy in `config/loader.py`: `AIConfig`, `VaultConfig`, `TelegramConfig`, `GitConfig`, `ScheduleConfig`, `AppConfig` — parse `config.yaml` via `pyyaml`
- [ ] T006 Add config validation in `config/loader.py`: vault path exists, `allowed_user_ids` not empty warning, `api_key` not empty when provider=anthropic, `processing_mode` enum check, `schedule.*.time` HH:MM format, `monthly_review.day` 1–28
- [ ] T007 [P] Implement `NoteType` enum in `vault_writer/vault/writer.py`: `NOTE`, `TASK`, `IDEA`, `JOURNAL`
- [ ] T008 [P] Implement `ProcessingMode` enum in `vault_writer/ai/provider.py`: `MINIMAL`, `BALANCED`, `FULL`
- [ ] T009 [P] Implement `VaultNote` dataclass in `vault_writer/vault/writer.py`: all fields per data-model.md including `title`, `date`, `categories`, `tags`, `moc`, `content`, `file_path`, `note_type`, `folder`, `note_number`
- [ ] T010 [P] Implement `ClassificationResult` dataclass in `vault_writer/ai/classifier.py`: `note_type`, `topic`, `folder`, `parent_moc`, `title`, `confidence`
- [ ] T011 [P] Implement `SessionStats` dataclass in `config/loader.py`: `tokens_consumed`, `last_note_path`, `notes_saved_today`, `vault_notes_total`
- [ ] T012 [P] Create `AIProvider` abstract base class in `vault_writer/ai/provider.py` with single method `complete(prompt: str, max_tokens: int) -> str`
- [ ] T013 Implement `AnthropicProvider(AIProvider)` in `vault_writer/ai/anthropic_provider.py`: use `anthropic` SDK, pass `api_key` from config, call `client.messages.create()`, return `response.content[0].text`
- [ ] T014 [P] Create stub `OllamaProvider(AIProvider)` in `vault_writer/ai/ollama_provider.py` that raises `NotImplementedError` — placeholder for v1.1
- [ ] T015 Implement `config/loader.py` `get_ai_provider(config: AppConfig) -> AIProvider` factory function: returns `AnthropicProvider` or raises for `ollama`
- [ ] T016 [P] Create `logs/` directory and set up logging in `config/loader.py`: file + console handlers, respect `logging.level`, `logging.log_path`, `logging.log_to_file` — **never log `api_key` or `bot_token`**

**Checkpoint**: Config loads, enums and dataclasses defined, AIProvider returns responses from Anthropic. All user stories can now begin.

---

## Phase 3: User Story 1 — Telegram Capture → Structured Vault Note (Priority: P1) 🎯 MVP

**Goal**: User sends message to Telegram bot → structured `.md` note saved in vault → bot confirms with file path.

**Independent Test**: Start bot, send `"дізнався що CQRS розділяє read і write моделі"` in Telegram → verify `.md` file exists in vault with correct frontmatter, MoC updated, bot replied with file path.

### Vault Layer

- [x] T017 [P] [US1] Implement `vault/indexer.py` `VaultIndex` dataclass and `build_index(vault_path: str) -> VaultIndex`: walk vault directory, parse YAML frontmatter from each `.md` file, populate `notes`, `mocs`, `topics`, `tags`, `total_notes`, `last_updated`
- [x] T018 [P] [US1] Implement `vault/reader.py` `read_frontmatter(file_path: str) -> dict`: parse YAML block between `---` delimiters at top of `.md` file
- [x] T019 [US1] Implement `vault/writer.py` `_write_lock = threading.Lock()` and `next_note_number(folder: Path) -> int`: scan existing `NNNN *.md` files, return `max + 1`, all under lock
- [x] T020 [US1] Implement `vault/writer.py` `write_note(note: VaultNote, vault_path: str) -> str`: build frontmatter YAML + markdown body (Description / Conclusions / Links sections), write file, return vault-relative path — under `_write_lock`
- [x] T021 [US1] Implement `vault/writer.py` `create_folder_if_missing(folder: Path)`: `folder.mkdir(parents=True, exist_ok=True)`
- [x] T022 [US1] Implement `vault/writer.py` `update_moc(moc_path: str, note_path: str, note_title: str, vault_path: str)`: read MoC file, append `- [[NNNN Title]]` under `## 🔑 Main sections`, write back
- [x] T023 [US1] Implement `vault/writer.py` `create_moc_if_missing(topic: str, vault_path: str) -> str`: if `0 {topic}.md` does not exist, create it from MoC template; return vault-relative path
- [x] T024 [US1] Implement `vault/indexer.py` `update_index(index: VaultIndex, note: VaultNote)`: insert/replace single note entry in `index.notes`, update `topics`, `tags`, `total_notes`, `last_updated` — O(1)

### AI Layer

- [x] T025 [US1] Implement `ai/classifier.py` `classify(text: str, provider: AIProvider, vault_index: VaultIndex, config: AppConfig) -> ClassificationResult`: build prompt injecting `AGENTS.md` + `skills/classifier.md` + vault topics, call `provider.complete()`, parse JSON response (`type`, `topic`, `folder`, `parent_moc`, `title`, `confidence`)
- [x] T026 [US1] Implement `ai/formatter.py` `format_note(text: str, classification: ClassificationResult, provider: AIProvider, config: AppConfig) -> str`: build prompt injecting `AGENTS.md` + `skills/vault-writer.md` + `skills/obsidian-rules.md`, return formatted markdown body
- [x] T075 [US1] Implement `ai/enricher.py` `add_wikilinks(text: str, index: VaultIndex, config: AppConfig) -> str`: scan vault index for related notes by topic/tag overlap, inject `[[NNNN Title]]` wikilinks for top `enrichment.max_related_notes` matches — called only in `full` processing mode (FR-011)
- [x] T027 [US1] Implement prefix detection in `telegram/handlers/message.py` `detect_prefix(text: str, prefixes: dict) -> tuple[NoteType | None, str]`: case-insensitive match against all configured prefixes, return `(NoteType, stripped_text)` or `(None, text)`
- [x] T028 [US1] Implement `vault_writer/tools/create_note.py` `handle_create_note(text, type_, folder, config, index, stats) -> dict`: orchestrate full flow — detect type → classify (if needed) → format (if balanced/full) → write → update index → update MoC → return output dict per `contracts/mcp-tools.md`

### Git Sync

- [x] T029 [US1] Implement `git_sync/sync.py` `commit_note(vault_path: str, file_path: str, config: GitConfig)`: stage file, commit with `vault: auto-save {date} {time}` message using `gitpython`
- [x] T030 [US1] Implement `git_sync/sync.py` `push_if_due(vault_path: str, config: GitConfig, last_push: datetime) -> datetime`: push to remote if `push_interval_minutes` elapsed, return updated `last_push`, silently continue if remote unreachable

### Telegram Bot

- [x] T031 [US1] Implement `telegram/bot.py` `build_application(config: AppConfig) -> Application`: create PTB `Application`, register all handlers, configure job queue
- [x] T032 [US1] Implement `telegram/handlers/commands.py` `auth_check(update, config) -> bool`: return `False` and log warning if `update.effective_user.id` not in `allowed_user_ids`
- [x] T033 [US1] Implement `telegram/handlers/message.py` `handle_message(update, context)`: auth check → send typing indicator (`send_chat_action("typing")`) → detect prefix or route to AI classify → call `handle_create_note` → reply with confirmation
- [x] T034 [US1] Implement `telegram/handlers/commands.py` slash command handlers: `/note`, `/task`, `/idea`, `/journal` — each does auth check + typing indicator + `handle_create_note` with explicit type
- [x] T035 [US1] Implement `telegram/handlers/commands.py` `/help` handler: reply with formatted command list
- [x] T036 [US1] Implement `telegram/formatter.py` `format_confirmation(file_path: str) -> str`: return `✓ Збережено → {file_path}`
- [x] T037 [US1] Implement Telegram rate-limit retry in `telegram/handlers/message.py`: catch `telegram.error.RetryAfter`, `asyncio.sleep(2**attempt)` up to 3 attempts, notify user if all fail
- [x] T068 [US1] Implement `config/loader.py` `update_processing_mode(config_path: str, mode: ProcessingMode)`: safe YAML rewrite preserving all other fields — **must exist before T062**
- [x] T062 [US1] Add `/mode` config hot-write in `telegram/handlers/commands.py`: call `update_processing_mode()`, reply with `✓ Режим змінено на: {mode}` + restart warning per contracts/telegram-commands.md (FR-013)
- [x] T069 [US1] Implement `telegram/handlers/commands.py` `/status` handler: build and send `SessionStats` response per `contracts/telegram-commands.md` format (provider, model, session tokens, last note, notes today, vault total)

### MCP Server

- [x] T038 [US1] Implement `vault_writer/server.py` MCP server entry point: register `create_note` and `get_vault_index` tools using `mcp` SDK `@app.list_tools()` / `@app.call_tool()`, stdio transport
- [x] T039 [US1] Implement `vault_writer/tools/get_vault_index.py` `handle_get_vault_index(index: VaultIndex) -> dict`: return snapshot per `contracts/mcp-tools.md`

### Setup & Launch

- [x] T040 [US1] Create `.brain/AGENTS.md` template with Obsidian vault writing instructions (English): note structure rules, frontmatter format, MoC linking rules, wikilink conventions
- [x] T041 [US1] [P] Create `.brain/skills/vault-writer.md`: VaultWriter-specific instructions (folder naming, sequential numbering, MoC update rules)
- [x] T042 [US1] [P] Create `.brain/skills/classifier.md`: classification guidelines (topic detection, confidence scoring, folder mapping)
- [x] T043 [US1] [P] Create `.brain/skills/obsidian-rules.md`: Obsidian-specific rules (frontmatter fields, tags plural form, wikilink syntax)
- [x] T044 [US1] Implement `setup.py`: interactive prompts → generate `config.yaml`, copy `.brain/` templates, build vault index, test Telegram + AI connections, generate `start.bat` / `start.sh`, start bot
- [x] T045 [US1] Create `start.bat`: activate `.venv`, run `python main.py`
- [x] T046 [US1] [P] Create `start.sh`: activate `.venv`, run `python main.py`
- [x] T047 [US1] Implement `main.py`: load config → build vault index → init SessionStats → start Telegram bot (blocking `application.run_polling()`). **NOTE: MCP server is a separate standalone process** — `vault_writer/server.py` is launched independently (e.g., by Claude Code via mcp_servers.json). Do NOT start MCP server as a thread here — MCP stdio transport owns stdin/stdout and is incompatible with PTB's event loop in the same process.

**Checkpoint**: User Story 1 fully functional — bot captures notes end-to-end. Run quickstart.md validation checklist.

---

## Phase 4: User Story 2 — Search Vault via Telegram (Priority: P2)

**Goal**: User sends `/search <query>` → bot replies with matching notes list with excerpts.

**Independent Test**: Send `/search Redis` → verify bot replies with matching note paths and excerpts.

- [x] T048 [P] [US2] Implement `vault_writer/tools/search_notes.py` `handle_search_notes(query: str, limit: int, folder: str | None, index: VaultIndex, vault_path: str) -> dict`: case-insensitive substring search across `title` + `content` of each note in index, compute simple TF score, return sorted results per `contracts/mcp-tools.md`, zero AI calls
- [x] T049 [US2] Implement `vault/reader.py` `read_note_content(file_path: str, vault_path: str) -> str`: read `.md` file, return body after frontmatter block (used for excerpt extraction)
- [x] T050 [US2] Implement `telegram/handlers/commands.py` `/search` handler: auth check → call `handle_search_notes` → format results with `telegram/formatter.py` → reply
- [x] T051 [US2] Implement `telegram/formatter.py` `format_search_results(results: list, query: str) -> str`: `🔍 Знайдено N нотаток для "{query}":\n\n1. {path}\n   ...{excerpt}...`; empty case: `Нічого не знайдено для "{query}"`
- [x] T052 [US2] Register `search_notes` tool in `vault_writer/server.py` MCP tool list

**Checkpoint**: User Stories 1 AND 2 independently functional.

---

## Phase 5: User Story 3 — Scheduled Summaries (Priority: P3)

**Goal**: Bot automatically sends daily/weekly/monthly Telegram summaries at configured times.

**Independent Test**: Set `daily_summary.time` to 2 minutes from now, restart bot → verify summary message arrives with today's notes and pending tasks.

- [x] T053 [US3] Implement `telegram/handlers/schedule.py` `get_pending_tasks(vault_path: str, index: VaultIndex) -> list[str]`: scan all `task`-type note files, regex `r'^- \[ \] (.+)$'` (multiline), return list of pending task texts — zero AI calls
- [x] T054 [US3] Implement `telegram/handlers/schedule.py` `daily_summary_job(context)`: get today's notes from `SessionStats` + index, get pending tasks, format message, send to `allowed_user_ids[0]`
- [x] T055 [US3] Implement `telegram/handlers/schedule.py` `weekly_summary_job(context)`: count notes added this week (by `date` frontmatter field), group by topic, format message, send
- [x] T056 [US3] Implement `telegram/handlers/schedule.py` `monthly_summary_job(context)`: count notes added this month by filtering `index.notes` where `date` frontmatter field is within current calendar month, list new topics introduced this month, compute vault growth as `(this month count)` — no log parsing needed, format, send
- [x] T057 [US3] Register scheduled jobs in `telegram/bot.py` `build_application()`: `job_queue.run_daily(daily_summary_job, time=config.schedule.daily_summary_time)` etc., only if enabled in config

**Checkpoint**: All three scheduled summary types fire at configured times.

---

## Phase 6: User Story 4 — Interactive Setup Installer (Priority: P4)

*Note: `setup.py` scaffold was created in Phase 3 (T044). This phase completes full installer polish.*

**Goal**: New user runs `python setup.py` → config created, vault indexed, bot starts → within 5 minutes.

**Independent Test**: Delete `config.yaml`, run `python setup.py`, answer all prompts → verify config created, bot starts, Telegram test message received.

- [x] T058 [US4] Add vault path existence validation in `setup.py`: prompt again if path not found, show clear error before exiting
- [x] T059 [US4] Add Telegram connection test in `setup.py`: send test message `"BrainSync setup complete ✓"` to configured user ID, confirm delivery
- [x] T060 [US4] Add AI provider connection test in `setup.py`: call `provider.complete("ping")` with short max_tokens, confirm response
- [x] T061 [US4] Add git remote test in `setup.py` (if git enabled): `git ls-remote {remote_url}`, warn if unreachable but do not abort

**Checkpoint**: User Story 4 fully functional — new user can complete setup in <5 minutes (SC-007).

---

## Phase 7: User Story 5 — Claude Code MCP Integration (Priority: P5)

**Goal**: VaultWriter registered as MCP server in Claude Code; `create_note` callable from coding session.

**Independent Test**: Add VaultWriter to `.claude/mcp_servers.json` in a test project, open Claude Code, call `create_note` with sample text → verify note appears in vault.

- [ ] T063 [US5] Verify `vault_writer/server.py` runs as standalone stdio MCP process: `python vault_writer/server.py` should start without error and respond to MCP `initialize` handshake
- [ ] T064 [US5] Implement `vault_writer/tools/classify_content.py` `handle_classify_content(text: str, provider, index, config) -> dict`: call `ai/classifier.py`, return result per `contracts/mcp-tools.md`
- [ ] T065 [US5] Register `classify_content` and `update_moc` tools in `vault_writer/server.py` MCP tool list
- [ ] T066 [US5] Update `quickstart.md` with Claude Code registration section: `.claude/mcp_servers.json` snippet, test procedure
- [ ] T067 [US5] Add Claude Code session token limit check in `vault_writer/tools/create_note.py`: if `claude_code.max_session_tokens` exceeded, return error response, skip write

**Checkpoint**: All 5 MCP tools registered and callable from Claude Code session.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Hardening, observability, and cross-story improvements.

- [ ] T070 [P] Implement AI API fallback in `vault_writer/tools/create_note.py`: on any `anthropic.APIError`, catch exception, set mode to `MINIMAL`, save note as-is, append fallback warning to Telegram reply
- [ ] T071 [P] Add structured logging throughout: `vault/writer.py` logs file path on every write; `ai/classifier.py` logs `type`, `folder`, `confidence` when `log_ai_decisions: true` (never log note content or API keys); Telegram handlers log unauthorised access attempts
- [ ] T072 [P] Implement `git_sync/sync.py` push failure silent handling: wrap `origin.push()` in try/except, log warning, update `last_push` timestamp only on success
- [ ] T073 Run `quickstart.md` validation checklist end-to-end: all 6 checklist items green
- [ ] T074 [P] Verify `.gitignore` covers `config.yaml`, `.venv/`, `logs/`, `__pycache__/`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Phase 2 — largest phase, must complete before other stories can integrate
- **US2 (Phase 4)**: Depends on Phase 2 + vault index from US1 — can start after T017/T018 complete
- **US3 (Phase 5)**: Depends on Phase 2 + SessionStats from US1 — can start after T011 complete
- **US4 (Phase 6)**: Depends on setup.py scaffold from US1 (T044) — polish only
- **US5 (Phase 7)**: Depends on MCP server from US1 (T038) — extend existing server
- **Polish (Phase 8)**: Depends on all desired stories complete

### Within Each User Story

- Vault layer tasks (T017–T024) before AI layer (T025–T028)
- AI layer before Telegram handlers (T031–T037)
- Handlers before MCP tools (T038–T039)
- All implementation before setup/launch (T040–T047)

### Parallel Opportunities (Phase 3 / US1)

```bash
# All can start simultaneously after Phase 2:
Task: "T017 Implement VaultIndex + build_index in vault_writer/vault/indexer.py"
Task: "T018 Implement read_frontmatter in vault_writer/vault/reader.py"
Task: "T012 AIProvider abstract base class in vault_writer/ai/provider.py"
Task: "T040 Create .brain/AGENTS.md template"
Task: "T041 Create .brain/skills/vault-writer.md"
Task: "T042 Create .brain/skills/classifier.md"
Task: "T043 Create .brain/skills/obsidian-rules.md"
```

---

## Implementation Strategy

### MVP First (Phase 1 + 2 + 3 only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational — **BLOCKS everything**
3. Complete Phase 3: User Story 1 (T017–T047)
4. **STOP AND VALIDATE**: Run quickstart.md checklist — bot captures notes end-to-end
5. Deploy / use daily

### Incremental Delivery

1. Setup + Foundational → infrastructure ready
2. US1 (Phase 3) → MVP: note capture works ✓
3. US2 (Phase 4) → add search ✓
4. US3 (Phase 5) → add scheduled summaries ✓
5. US4 (Phase 6) → polished installer ✓
6. US5 (Phase 7) → Claude Code integration ✓
7. Polish (Phase 8) → production-ready ✓

---

## Notes

- `[P]` = different files, no blocking dependencies — safe to run in parallel
- `[Story]` maps task to user story for traceability
- No test tasks generated (not requested in spec)
- Commit after each completed checkpoint
- Total tasks: **75** (T001–T075; T062/T068/T069 moved from Phase 6/8 to Phase 3; T075 added for enricher)
- Phase 3 (US1) is the largest — 34 tasks — contains full end-to-end MVP
