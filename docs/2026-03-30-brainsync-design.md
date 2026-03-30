# BrainSync — Design Document

**Date:** 2026-03-30
**Status:** Approved
**Spec:** `specs/brainsync-v1.md`

---

## Summary

BrainSync is a local AI-powered personal knowledge management system. It connects Telegram (and other sources) to an Obsidian vault via a VaultWriter MCP server. Claude AI classifies, formats, and enriches notes — placing them correctly into the vault structure with proper MOC links, frontmatter, and wikilinks.

---

## Architecture

```
Telegram Bot ──────┐
                   ▼
Claude Code ──▶ VaultWriter MCP Server
                   │
                   ├── vault/indexer.py   (in-memory index)
                   ├── ai/classifier.py   (Claude API)
                   ├── ai/formatter.py    (Claude API)
                   ├── ai/enricher.py     (Claude API, full mode only)
                   └── vault/writer.py    (direct .md file I/O)
                             │
                             ▼
                    Obsidian Vault (C:\SecondaryBrain)
                             │
                             ▼
                        git_sync/sync.py → GitHub/GitLab
```

---

## Key Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Vault I/O | Direct Python file I/O | Faster, no Obsidian dependency |
| Obsidian CLI | Optional, for Dataview/backlinks only | Unique value not replaceable by Python |
| AI role | Classify + format + enrich | Not file I/O, only where "understanding" needed |
| Provider abstraction | `AIProvider` interface | Swap Anthropic ↔ Ollama via config |
| Instructions | `.brain/AGENTS.md` + `skills/*.md` | Universal, works with any AI |
| Config vs instructions | Config = parameters, AGENTS.md = static rules | Clean separation |
| Claude Code integration | Manual only (v1) | Auto too expensive on long sessions |

---

## Processing Flow (single message)

```
1. User sends message in Telegram
2. telegram/handlers/message.py — detect command/prefix
3. vault/indexer.py — get vault context
4. ai/classifier.py — [0-1 AI calls] → type, folder, MoC
5. ai/formatter.py  — [0-1 AI calls, balanced+] → formatted .md
6. ai/enricher.py   — [0-1 AI calls, full only] → wikilinks
7. vault/writer.py  — write file, update MoC [0 AI calls]
8. git_sync/sync.py — commit [0 AI calls]
9. Telegram reply   — "✓ Збережено → Architecture/0004 CQRS.md"
```

**AI calls per message:**
- `/task text` with prefix → 0 calls
- minimal mode → 0-1 calls
- balanced mode → 1-2 calls
- full mode → 2-3 calls

---

## Project Structure

```
C:\Projects\BrainSync\
├── config.yaml
├── main.py
├── setup.py
├── .brain/
│   ├── AGENTS.md                  # universal AI instructions (English)
│   ├── skills/
│   │   ├── vault-writer.md
│   │   ├── classifier.md
│   │   └── obsidian-rules.md
│   └── context/
│       └── vault-index.md         # auto-generated
├── vault_writer/
│   ├── server.py                  # MCP server
│   ├── tools/
│   │   ├── create_note.py
│   │   ├── search_notes.py
│   │   ├── update_moc.py
│   │   └── classify_content.py
│   ├── ai/
│   │   ├── provider.py            # AIProvider interface
│   │   ├── anthropic_provider.py
│   │   ├── ollama_provider.py     # v1.1
│   │   ├── classifier.py
│   │   ├── formatter.py
│   │   └── enricher.py
│   └── vault/
│       ├── reader.py
│       ├── writer.py
│       └── indexer.py
├── telegram/
│   ├── bot.py
│   ├── handlers/
│   │   ├── message.py
│   │   ├── commands.py
│   │   └── schedule.py
│   └── formatter.py
├── git_sync/
│   └── sync.py
├── integrations/
│   ├── obsidian_cli/
│   └── notebooklm/                # v1.1+
├── specs/
│   └── brainsync-v1.md
├── docs/
│   └── 2026-03-30-brainsync-design.md
└── logs/
    └── vault.log
```

---

## config.yaml (full)

```yaml
ai:
  provider: anthropic
  model: claude-sonnet-4-6
  ollama_url: http://localhost:11434
  processing_mode: balanced
  agents_file: .brain/AGENTS.md
  skills_path: .brain/skills/
  inject_vault_index: true
  max_context_tokens: 4000

vault:
  path: C:\SecondaryBrain
  language: uk

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
  remote: origin
  branch: main
  push_interval_minutes: 30

schedule:
  daily_summary:
    enabled: true
    time: "21:00"
  weekly_review:
    enabled: true
    day: sunday
    time: "20:00"
  monthly_review:
    enabled: true
    day: 1
    time: "10:00"

claude_code:
  enabled: false
  capture_trigger: manual
  save_raw: true
  max_session_tokens: 2000
  allowed_projects: []

integrations:
  obsidian_cli:
    enabled: true
    use_for:
      - dataview_queries
      - backlinks
  notebooklm:
    enabled: false

logging:
  level: info
  log_to_file: true
  log_path: logs/vault.log
  log_ai_decisions: true
```

---

## Roadmap

| Phase | Features | Priority |
|-------|----------|----------|
| 1 | VaultWriter MCP, Telegram bot, Git sync, setup.py | MVP |
| 2 | Enrichment (full mode), /search, Obsidian CLI | High |
| 3 | Claude Code integration | Medium |
| 4 | Daily/weekly/monthly summaries | Medium |
| 5 | Ollama, NotebookLM, /open command | Future |
