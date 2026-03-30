<!--
SYNC IMPACT REPORT
==================
Version change: (unversioned template) → 1.0.0
Modified principles: N/A (initial population)
Added sections:
  - Core Principles (I–V)
  - Security & Privacy
  - Configuration & Instructions
  - Governance
Templates reviewed:
  - .specify/templates/spec-template.md ✅ compatible (no changes needed)
  - .specify/templates/plan-template.md ✅ compatible — Constitution Check gates align with principles
  - .specify/templates/tasks-template.md ✅ compatible — task phases match phased roadmap approach
Deferred TODOs: none
-->

# BrainSync Constitution

## Core Principles

### I. Local-First Architecture

The system MUST run entirely on the user's local machine. No user data, vault content,
or note text MUST be transmitted to any third party except the explicitly configured AI
provider API (Anthropic or Ollama). Ollama runs locally by default and is preferred when
privacy is the primary concern. All file I/O, indexing, and git operations MUST execute
locally without cloud dependencies.

**Rationale**: The vault is a personal second brain containing sensitive personal, professional,
and health information. Local-first guarantees the user retains full control at all times.

### II. AI as Intelligence Layer Only

AI MUST be used exclusively for tasks that require semantic understanding: classification,
formatting, and enrichment of note content. AI MUST NOT be used for file I/O, vault
indexing, git operations, or any deterministic task replaceable by direct Python code.
The number of AI API calls per operation MUST be minimized via processing modes
(`minimal` → 0–1, `balanced` → 1–2, `full` → 2–3). When a user provides an explicit
`/command` or `prefix:`, AI classification MUST be skipped entirely (0 calls).

**Rationale**: Unnecessary AI calls increase cost and latency. The system serves a single
user with real-time expectations; every avoidable call degrades the experience.

### III. Provider Abstraction (Non-Negotiable)

All AI calls MUST go through the `AIProvider` interface (`provider.py`). No component
MUST import `anthropic` or `ollama` libraries directly — only via the concrete provider
classes (`AnthropicProvider`, `OllamaProvider`). Switching providers MUST require only
a `config.yaml` change, with zero code modifications.

**Rationale**: Vendor lock-in risk is real. Anthropic pricing or availability may change.
The abstraction is the primary architectural guard against forced rewrites.

### IV. VaultWriter as Single Write Gateway

All writes to the Obsidian vault MUST go through the VaultWriter MCP server. No component
(Telegram bot, git sync, setup, Claude Code integration) MUST write `.md` files to the
vault directly, bypassing VaultWriter. The in-memory vault index MUST be updated after
every write. MoC linking and frontmatter generation are VaultWriter responsibilities only.

**Rationale**: A single write gateway ensures consistent note structure, prevents duplicate
filenames (race condition protection via sequential numbering), and keeps the vault index
authoritative.

### V. Configuration Drives Behavior; Instructions Drive AI

Runtime parameters (vault path, model, processing mode, git settings, schedule times)
MUST live in `config.yaml`. Static AI behavioral rules (note conventions, formatting
standards, Obsidian structure guidelines) MUST live in `.brain/AGENTS.md` and
`.brain/skills/*.md`. These two domains MUST NOT be mixed: `config.yaml` MUST contain
no prose AI instructions; `AGENTS.md` MUST contain no runtime-variable parameters.

**Rationale**: Clean separation allows tuning AI behavior without touching code or config,
and changing operational parameters without touching prompts. It also makes the instruction
set portable to any AI agent (Claude Code, future agents).

## Security & Privacy

- Telegram bot MUST ignore all messages from user IDs not listed in `telegram.allowed_user_ids`.
  If the list is empty, the bot MUST refuse all messages and log a startup warning.
- API keys (Anthropic, Telegram bot token) MUST be stored only in `config.yaml` and
  MUST NOT appear in logs, console output, git commits, or AI prompts.
- `config.yaml` MUST be listed in `.gitignore` to prevent accidental credential exposure.
- `logging.log_ai_decisions` when enabled MUST log only classification metadata (type,
  folder, confidence), never raw note content or API keys.

## Development Constraints

- **Language**: Python 3.12+ on Windows 11. No platform-specific APIs that break cross-OS
  portability unless explicitly justified.
- **MCP protocol**: VaultWriter exposes tools via the MCP standard; the server MUST be
  registerable in any project's `.claude/mcp_servers.json` without modification.
- **Phased delivery**: Implementation MUST follow the 5-phase roadmap. Phase 1 (MVP) MUST
  be independently deployable and testable before Phase 2 work begins.
- **Simplicity over abstraction**: Introduce abstractions only when two or more concrete
  use cases exist. No speculative generalization.
- **Fallback behavior**: When an external dependency fails (AI API, git remote, Obsidian CLI),
  the system MUST degrade gracefully (save in minimal mode, skip push, fall back to direct
  file ops) rather than halt or lose user data.

## Governance

This constitution supersedes all other written or verbal agreements about BrainSync's
architecture, security posture, and development discipline. Amendments require:
1. A documented rationale (why the current principle is insufficient or wrong).
2. A version bump following semantic versioning:
   - **MAJOR**: Principle removal, redefinition, or backward-incompatible governance change.
   - **MINOR**: New principle or section added; material expansion of existing guidance.
   - **PATCH**: Clarification, wording improvement, typo fix.
3. An updated `LAST_AMENDED_DATE`.

All implementation plans (`/speckit.plan`) MUST include a Constitution Check gate that
verifies the proposed design does not violate Principles I–V before Phase 1 work begins.
Complexity violations MUST be justified in the plan's Complexity Tracking table.

**Version**: 1.0.0 | **Ratified**: 2026-03-30 | **Last Amended**: 2026-03-30
