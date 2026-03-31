# Config Schema Contract: config.yaml (v1.1 — Media Support)

**Branch**: `002-media-support` | **Date**: 2026-03-31
**Extends**: `specs/001-brainsync-mvp/contracts/config-schema.md`

---

## Changes from v1.0

| Change | Field | Description |
|--------|-------|-------------|
| New field | `ai.ollama_vision_model` | Optional Ollama model for photo processing |
| New block | `media` | All media processing configuration |

---

## Full Schema (v1.1)

```yaml
ai:
  provider: "anthropic"           # "anthropic" | "ollama"
  model: "claude-sonnet-4-6"      # Anthropic model ID or Ollama text model name
  ollama_url: "http://localhost:11434"   # Ollama base URL (used when provider = "ollama")
  ollama_vision_model: ""         # NEW: Ollama vision model (e.g. "llava"); empty = vision disabled
  processing_mode: "balanced"     # "minimal" | "balanced" | "full"
  agents_file: ".brain/AGENTS.md"
  skills_path: ".brain/skills/"
  inject_vault_index: true
  max_context_tokens: 4000
  api_key: ""                     # Anthropic API key — NEVER logged or committed

vault:
  path: "C:\\SecondaryBrain"
  language: "uk"

media:                            # NEW BLOCK
  max_voice_duration_seconds: 300 # Reject voice messages longer than this (seconds)
  transcription_model: "small"    # Whisper model size: tiny | base | small | medium | large
  pdf_max_pages: 50               # Extract at most this many pages from a PDF
  pdf_ai_context_chars: 3000      # Characters of PDF text sent to AI for classification
  max_file_size_mb: 20            # Maximum Telegram file download size (MB)

enrichment:
  add_wikilinks: true
  update_moc: true
  max_related_notes: 5
  scan_vault_on_start: true

telegram:
  bot_token: ""
  allowed_user_ids: []

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
    time: "21:00"
  weekly_review:
    enabled: true
    day: "sunday"
    time: "20:00"
  monthly_review:
    enabled: true
    day: 1
    time: "10:00"

claude_code:
  enabled: false
  capture_trigger: "manual"
  save_raw: true
  max_session_tokens: 2000
  allowed_projects: []

integrations:
  obsidian_cli:
    enabled: true
    use_for: ["dataview_queries", "backlinks"]
  notebooklm:
    enabled: false

logging:
  level: "info"
  log_to_file: true
  log_path: "logs/vault.log"
  log_ai_decisions: true
```

---

## Validation Rules (additions to v1.0)

| Field | Rule |
|-------|------|
| `ai.ollama_vision_model` | Optional string; if non-empty and `provider = "ollama"`, used for vision calls |
| `media.max_voice_duration_seconds` | Integer > 0; default 300 |
| `media.transcription_model` | Must be one of: `tiny`, `base`, `small`, `medium`, `large` |
| `media.pdf_max_pages` | Integer > 0; default 50 |
| `media.pdf_ai_context_chars` | Integer > 0; default 3000 |
| `media.max_file_size_mb` | Integer 1–50; default 20 |

---

## Transcription Model Reference

| Model | Disk Size | Speed | Ukrainian Quality |
|-------|-----------|-------|-------------------|
| `tiny` | ~75 MB | fastest | basic |
| `base` | ~145 MB | fast | good |
| `small` | ~466 MB | moderate | **recommended** |
| `medium` | ~1.5 GB | slow | excellent |
| `large` | ~3 GB | slowest | best |

Default `small` is the recommended balance of size, speed, and Ukrainian accuracy.

---

## Security Constraints

All v1.0 security constraints apply. Additional:
- Downloaded Telegram media files MUST be deleted from the local temp directory immediately after processing, regardless of success or failure.
- `ai.ollama_vision_model` value is non-sensitive and may appear in logs.
