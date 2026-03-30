# Config Schema Contract: config.yaml

**Branch**: `001-brainsync-mvp` | **Date**: 2026-03-30

---

## Full Schema

```yaml
ai:
  provider: "anthropic"           # "anthropic" | "ollama"
  model: "claude-sonnet-4-6"      # Anthropic model ID
  ollama_url: "http://localhost:11434"  # Only used when provider = "ollama"
  processing_mode: "balanced"     # "minimal" | "balanced" | "full"
  agents_file: ".brain/AGENTS.md" # Relative to project root
  skills_path: ".brain/skills/"   # Relative to project root
  inject_vault_index: true        # Inject vault structure into AI prompts
  max_context_tokens: 4000        # Max tokens for vault context injection
  api_key: ""                     # Anthropic API key — NEVER logged or committed

vault:
  path: "C:\\SecondaryBrain"      # Absolute path to Obsidian vault
  language: "uk"                  # Note language for AI formatting prompts

enrichment:
  add_wikilinks: true             # Enable wikilink enrichment in full mode
  update_moc: true                # Auto-update parent MoC on note creation
  max_related_notes: 5            # Max wikilinks to add in full mode
  scan_vault_on_start: true       # Rebuild vault index at startup

telegram:
  bot_token: ""                   # Telegram bot token — NEVER logged or committed
  allowed_user_ids: []            # List of authorised Telegram user IDs (integers)

prefixes:
  note: ["нотатка:", "note:"]
  task: ["задача:", "task:", "todo:"]
  idea: ["ідея:", "idea:"]
  journal: ["день:", "journal:"]

git:
  enabled: true
  auto_commit: true
  commit_message: "vault: auto-save {date} {time}"
  push_remote: true
  remote: "origin"
  branch: "main"
  push_interval_minutes: 30

schedule:
  daily_summary:
    enabled: true
    time: "21:00"                 # HH:MM local time
  weekly_review:
    enabled: true
    day: "sunday"                 # "monday" .. "sunday"
    time: "20:00"
  monthly_review:
    enabled: true
    day: 1                        # Day of month: 1–28
    time: "10:00"

claude_code:
  enabled: false
  capture_trigger: "manual"       # "manual" only in v1
  save_raw: true
  max_session_tokens: 2000
  allowed_projects: []            # [] = all projects allowed

integrations:
  obsidian_cli:
    enabled: true
    use_for: ["dataview_queries", "backlinks"]
  notebooklm:
    enabled: false                # Out of scope v1

logging:
  level: "info"                   # "debug" | "info" | "warn" | "error"
  log_to_file: true
  log_path: "logs/vault.log"
  log_ai_decisions: true          # Logs type/folder/confidence only — never note content
```

---

## Validation Rules

| Field | Rule |
|-------|------|
| `ai.provider` | Must be `"anthropic"` or `"ollama"` |
| `ai.processing_mode` | Must be `"minimal"`, `"balanced"`, or `"full"` |
| `vault.path` | Must exist as a directory at startup |
| `telegram.allowed_user_ids` | If empty list → log WARNING, refuse all messages |
| `schedule.*.time` | Must match `HH:MM` format |
| `schedule.monthly_review.day` | Must be integer 1–28 |
| `ai.api_key` | Must not be empty when `provider = "anthropic"` |
| `telegram.bot_token` | Must not be empty |

---

## Security Constraints

- `config.yaml` MUST be listed in `.gitignore`
- `ai.api_key` and `telegram.bot_token` MUST NOT appear in:
  - Log files
  - Console output
  - AI prompts
  - Git commits
- `logging.log_ai_decisions` logs ONLY: `type`, `folder`, `confidence` — never raw note text
