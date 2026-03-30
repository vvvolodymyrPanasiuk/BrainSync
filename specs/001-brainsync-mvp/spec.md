# Feature Specification: BrainSync — Personal Knowledge Automation System

**Feature Branch**: `001-brainsync-mvp`
**Created**: 2026-03-30
**Status**: Draft
**Input**: docs/2026-03-30-brainsync-design.md + specs/brainsync-v1.md

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Capture a thought from Telegram and have it saved as a structured note (Priority: P1)

The user is on the go and types a raw thought into their Telegram chat. Without any manual
formatting, the system automatically classifies the content, generates proper Obsidian
frontmatter, places the file in the correct folder, links it to the right Map of Content
(MoC), and replies with the saved file path. The user never opens Obsidian or touches the
vault directly.

**Why this priority**: This is the core value proposition. Everything else is secondary
to this flow working end-to-end.

**Independent Test**: Send a plain-text message to the Telegram bot; verify a correctly
structured `.md` file appears in the vault in the right folder with valid frontmatter and
a MoC backlink.

**Acceptance Scenarios**:

1. **Given** the bot is running and the user's Telegram ID is authorised,
   **When** the user sends `"дізнався що CQRS розділяє read і write моделі"` (no prefix),
   **Then** the system classifies it as a note in the Architecture folder, creates a file
   like `Architecture/0004 CQRS патерн.md` with correct frontmatter, updates the parent
   MoC, and replies `✓ Збережено → Architecture/0004 CQRS патерн.md`.

2. **Given** the user sends `/task купити молоко`,
   **Then** zero AI classification calls are made, the item is saved as a task, and the
   bot confirms with the file path.

3. **Given** the user sends `ідея: зробити дашборд для моніторингу`,
   **Then** the inline prefix is detected, type is set to `idea`, and AI classification
   is skipped.

4. **Given** an unknown Telegram user sends a message,
   **Then** the bot does NOT respond and logs the unauthorised attempt.

---

### User Story 2 — Search existing vault notes via Telegram (Priority: P2)

The user wants to find a note they captured previously. They send a search query from
Telegram and receive a list of matching notes with file paths and short excerpts —
without opening Obsidian.

**Why this priority**: Retrieval is the second half of the knowledge loop. Without search,
captured notes become inaccessible black boxes.

**Independent Test**: Send `/search Redis` and receive a list of vault notes containing
"Redis" with paths and excerpts.

**Acceptance Scenarios**:

1. **Given** the vault contains notes mentioning "Redis",
   **When** the user sends `/search Redis`,
   **Then** the bot replies with a formatted list of matching notes including file paths
   and a short excerpt from each.

2. **Given** no notes match the query,
   **Then** the bot replies with a friendly "no results found" message.

---

### User Story 3 — Automatic daily/weekly/monthly vault summaries (Priority: P3)

At configured times, the bot proactively sends a summary to the user's Telegram: today's
notes, pending tasks, weekly progress, or monthly vault growth — without the user
initiating anything.

**Why this priority**: Scheduled summaries close the review loop and increase knowledge
retention, but are not blocking for the core capture use case.

**Independent Test**: Configure daily summary for a near-future time; verify the bot
sends the expected message with today's notes and task counts.

**Acceptance Scenarios**:

1. **Given** `daily_summary` is enabled and the configured time is reached,
   **Then** the bot sends a message listing notes added today and pending tasks.

2. **Given** `weekly_review` is enabled and the configured day/time arrives,
   **Then** the bot sends a weekly summary with note count by topic and progress on goals.

3. **Given** `monthly_review` is enabled,
   **Then** the bot sends vault growth statistics (total notes, new topics) on the
   configured day.

---

### User Story 4 — First-time setup via interactive installer (Priority: P4)

A new user runs a single setup script in their terminal. They answer a series of prompts
(vault path, Telegram token, AI provider, processing mode, git settings) and the system
configures itself, indexes the vault, tests all connections, and starts the bot — without
editing any config files manually.

**Why this priority**: Onboarding friction must be low, but this does not block existing
users who configure manually.

**Independent Test**: Run `python setup.py` in a clean environment; verify config is
created, vault is indexed, and the bot starts successfully.

**Acceptance Scenarios**:

1. **Given** the user runs the setup script and answers all prompts,
   **Then** the configuration file is created, the vault is indexed, the Telegram
   connection is tested, and the bot starts.

2. **Given** the vault path entered does not exist,
   **Then** setup fails with a clear error message and does NOT start the bot.

---

### User Story 5 — Save vault notes from a Claude Code session via MCP (Priority: P5)

During a development session, the user explicitly saves a session note or architecture
decision to the vault using the VaultWriter MCP tool. The note lands in the correct vault
folder with full structure — without switching apps.

**Why this priority**: Additive capability that extends vault capture to development
contexts, but is not blocking for the Telegram workflow.

**Independent Test**: Connect to VaultWriter MCP and call `create_note`; verify the file
appears in the vault with correct structure and the tool returns the file path.

**Acceptance Scenarios**:

1. **Given** VaultWriter is registered as an MCP server,
   **When** `create_note` is called with raw text,
   **Then** a structured note appears in the vault and the tool returns the file path.

2. **Given** the session token limit is exceeded,
   **Then** saving is skipped and the user receives a notification.

---

### Edge Cases

- If the AI provider API call fails (timeout, rate limit, network error), the system saves
  the note in minimal mode as a fallback and notifies the user via Telegram.
- If the target folder in the vault does not exist, the system creates it before writing.
- If the parent MoC does not exist for a new topic, the system creates a new MoC file
  from the vault template before adding the link.
- If the git remote is unreachable during push, the system continues normally and retries
  on the next scheduled interval.
- If two notes are created simultaneously with conflicting sequential filenames, the second
  write increments the number until a unique name is found.
- If the Obsidian CLI integration is enabled but Obsidian is not running, the system falls
  back to direct file operations without error.
- If the authorised user ID list is empty, the bot refuses all messages and logs a startup
  warning.
- If the Telegram API returns a rate-limit error, the system MUST retry with exponential
  backoff up to 3 attempts. If all retries fail, the user MUST be notified of the failure
  (queued for next available delivery window).

---

## Clarifications

### Session 2026-03-30

- Q: When the user sends `/mode <minimal|balanced|full>`, is the change session-only or persisted? → A: Persisted — written to `config.yaml` immediately so it survives bot restarts.
- Q: What should happen when Telegram API rate limits are hit? → A: Retry with exponential backoff (up to 3 attempts); if all retries fail, notify the user of the failure.
- Q: What is the expected bot restart behavior on crash or OS reboot? → A: Simple script launch — no auto-restart. The user starts the bot manually by running the launch script; it stops when the terminal is closed or Ctrl+C is pressed.
- Q: What feedback does the user receive while an AI request is in progress? → A: Telegram typing indicator (sendChatAction) shown continuously until the final reply is sent.
- Q: What data should the `/status` command return? → A: Last saved note path, current processing mode, active AI provider, total AI tokens consumed in current session, vault context fill level (notes indexed / estimated token budget), and vault total note count.

### Session 2026-03-30 (pass 2)

- Q: Does switching AI providers require a service restart? → A: Yes — provider change takes effect after restarting the launch script (`start.bat` / `start.sh`). No hot-reload required.
- Q: How should the bot be run — Windows Service or simple script? → A: Simple bash/bat script; the bot runs while the terminal is open and stops when it is closed. No NSSM or Windows Service required.
- Q: How are "pending tasks" identified for daily summaries? → A: Use Obsidian Tasks plugin format — task items stored as `- [ ] text` (pending) and `- [x] text` (done) within task-type notes. The bot reads these via direct file regex scan (zero AI tokens). Compatible with Obsidian Tasks plugin when Obsidian is open.

---

## Requirements *(mandatory)*

### Functional Requirements

**VaultWriter MCP Server**

- **FR-001**: The system MUST provide a VaultWriter MCP server exposing five tools:
  `create_note`, `search_notes`, `update_moc`, `classify_content`, `get_vault_index`.
- **FR-002**: `create_note` MUST generate a properly structured note file with YAML
  frontmatter (`title`, `date`, `categories`, `tags`, `MoC`), wikilinks, and standard
  sections (Description, Conclusions, Links), placed in the correct vault folder.
- **FR-003**: `create_note` MUST update the parent MoC file by adding a wikilink to the
  new note when MoC-updating is enabled in configuration.
- **FR-004**: The server MUST maintain an in-memory vault index, built at startup and
  updated after every write, without requiring Obsidian to be running.
- **FR-005**: The server MUST support two AI providers switchable via configuration with
  no code changes.
- **FR-006**: The server MUST load the AI instruction file and relevant skill files and
  inject them into every AI prompt.

**AI Classification & Processing**

- **FR-007**: The system MUST support three processing modes:
  - `minimal` — classification only, note saved as-is (0–1 AI calls).
  - `balanced` — classification + formatting (1–2 AI calls).
  - `full` — classification + formatting + wikilink enrichment (2–3 AI calls).
- **FR-008**: When no prefix or slash command is provided, the system MUST use AI to
  classify content type, target folder, and parent MoC.
- **FR-009**: When a slash command or inline prefix is provided, the system MUST skip AI
  classification entirely (zero additional AI calls).
- **FR-010**: Classification MUST produce a structured result with: type, topic, folder,
  parent MoC, title, and confidence score (0.0–1.0).
- **FR-011**: In `full` mode, enrichment MUST link to at most the configured maximum
  number of existing vault notes via wikilinks.

**Telegram Bot**

- **FR-012**: The bot MUST only respond to user IDs listed in the authorised users
  configuration. All other senders MUST be silently ignored.
- **FR-013**: The bot MUST support slash commands: `/note`, `/task`, `/idea`, `/journal`,
  `/search`, `/mode`, `/status`, `/help`. The `/mode` command MUST immediately persist
  the selected processing mode to the configuration file so it survives bot restarts.
- **FR-014**: The bot MUST support inline Ukrainian and English prefixes as alternatives
  to slash commands (`нотатка:` / `note:`, `задача:` / `task:` / `todo:`,
  `ідея:` / `idea:`, `день:` / `journal:`).
- **FR-015**: Plain text without a command or prefix MUST be routed through AI
  classification.
- **FR-016**: After every save, the bot MUST reply with a confirmation message containing
  the vault-relative file path.
- **FR-016a**: While an AI processing request is in progress, the bot MUST send a Telegram
  typing indicator continuously until the final confirmation reply is delivered.
- **FR-016b**: The `/status` command MUST return: last saved note path, current processing
  mode, active AI provider, total AI tokens consumed in the current session, vault context
  fill level (indexed notes count vs. estimated token budget), and total vault note count.

**Git Sync**

- **FR-017**: When git sync is enabled, the system MUST commit all vault changes after
  every save operation using a consistent commit message format.
- **FR-018**: When remote push is enabled, the system MUST push to the configured remote
  on the configured interval.

**Scheduled Summaries**

- **FR-019**: When daily summary is enabled, the bot MUST send a Telegram message at the
  configured time listing notes added today and pending tasks. Pending tasks are identified
  by scanning task-type note files for unchecked Obsidian Tasks format items (`- [ ]`);
  completed items (`- [x]`) are excluded. This scan MUST use direct file parsing with
  zero AI calls. The format is compatible with the Obsidian Tasks plugin.
- **FR-020**: When weekly review is enabled, the bot MUST send a weekly summary with note
  count by topic and progress on active goals.
- **FR-021**: When monthly review is enabled, the bot MUST send monthly vault growth
  statistics.

**Claude Code Integration**

- **FR-022**: VaultWriter MUST be registerable as an MCP server in any Claude Code project
  without modifying the server itself.
- **FR-023**: In manual capture mode, the system MUST save to the vault only when
  explicitly called via the `create_note` tool.
- **FR-024**: When the session token limit is exceeded, the system MUST skip saving and
  notify the user.

**Setup Installer**

- **FR-025**: The installer MUST interactively collect: vault path, Telegram bot token,
  authorised user ID, AI provider, API key, processing mode, git preference, and git
  remote URL.
- **FR-026**: Setup MUST generate the configuration file, create AI instruction files from
  templates, index the vault, test all connections, generate a `start.bat` / `start.sh`
  launch script, and start the bot process.
- **FR-027**: If the vault path does not exist at setup time, the installer MUST fail with
  a clear error message and NOT start the bot.
- **FR-028**: The bot process MUST run in the foreground of the terminal. The user stops
  it by closing the terminal or pressing Ctrl+C. No auto-restart or background daemon is
  required. Scheduled summaries are only delivered while the bot process is running.

### Key Entities

- **VaultNote**: A single note file in the vault. Attributes: title, date, categories,
  tags, parent MoC link, content body, vault-relative file path, note type
  (note / task / idea / journal). Task-type notes store individual items as Obsidian
  Tasks format checkboxes: `- [ ] pending item` / `- [x] completed item`.
- **MoC (Map of Content)**: An index note that aggregates links to related notes under a
  topic. Created automatically when a new topic is first encountered.
- **VaultIndex**: In-memory snapshot of all notes, MoCs, topics, and tags. Rebuilt at
  startup and updated after each write.
- **ProcessingMode**: Enumerated setting (`minimal`, `balanced`, `full`) controlling the
  number of AI calls per message.
- **AIProvider**: Abstraction over supported AI services. Exposes a single text-completion
  method; concrete implementations are swapped via configuration.
- **ScheduledSummary**: A time-triggered message generated from vault data and sent to the
  user's Telegram.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can send a plain-text message and receive a vault file confirmation
  within 5 seconds (balanced mode, normal network conditions).
- **SC-002**: A user can save a note using a slash command with zero AI API calls made.
- **SC-003**: Full-text search returns relevant results within 3 seconds for a vault of up
  to 500 notes.
- **SC-004**: The system starts and completes vault indexing within 15 seconds on a
  standard PC.
- **SC-005**: Switching AI providers requires only a configuration file change and a
  bot restart (stop + re-run launch script) — no code modification.
- **SC-006**: An unauthorised Telegram user receives no response 100% of the time.
- **SC-007**: A first-time user can complete the interactive setup and have the bot
  running within 5 minutes of starting the installer.
- **SC-008**: In the event of an AI API failure, the note is saved (in minimal mode) and
  the user is notified — no data is lost.
- **SC-009**: Git commits are created automatically after every save when sync is enabled.
- **SC-010**: Daily, weekly, and monthly summaries are delivered at the configured times
  without manual triggering.

---

## Assumptions

- Single user only: the system is designed for exactly one Telegram user. Multi-user
  support is explicitly out of scope for v1.
- The Obsidian vault already exists at the configured path before setup runs.
- The vault follows established naming and structure conventions (numbered notes, MoC
  index files, standard frontmatter fields).
- Internet access is available for cloud AI API calls; local AI mode works fully offline.
- Git is already installed and the vault directory is already a git repository when git
  sync is enabled.
- Voice messages, images, and other Telegram media types are out of scope for v1 (text
  only).
- NotebookLM integration, local AI provider implementation, and auto-capture of coding
  sessions are deferred to v1.1+.
- Web UI is not planned for any version.
- The authorised Telegram user ID is known before setup and is provided during the
  installer flow.
- Notes are written in Ukrainian; code, configuration, and AI instructions are in English.

---

## Out of Scope (v1.0)

- NotebookLM integration
- Notion sync
- Local AI provider implementation (interface defined, implementation deferred to v1.1)
- `/open` command (open note in Obsidian via CLI)
- Auto-capture of full coding sessions
- Web UI
- Multi-user support
- Voice messages or media in Telegram
