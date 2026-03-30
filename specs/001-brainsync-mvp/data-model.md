# Data Model: BrainSync MVP

**Branch**: `001-brainsync-mvp` | **Date**: 2026-03-30

---

## 1. VaultNote

Represents a single `.md` file in the Obsidian vault.

```python
@dataclass
class VaultNote:
    title: str                          # Human-readable title
    date: str                           # ISO date: YYYY-MM-DD
    categories: list[str]               # e.g., ["Architecture"]
    tags: list[str]                     # e.g., ["areas/backend", "types/notes"]
    moc: str                            # Wikilink to parent MoC: "[[0 Architecture]]"
    content: str                        # Full markdown body (after frontmatter)
    file_path: str                      # Vault-relative path: "Architecture/0004 CQRS.md"
    note_type: NoteType                 # Enum: note | task | idea | journal
    folder: str                         # Vault-relative folder: "Architecture"
    note_number: int                    # Sequential number within folder: 4
```

**Filename convention**: `{note_number:04d} {title}.md`
- Regular notes: `0004 CQRS патерн.md`
- MoC files: `0 Architecture.md`
- Detailed articles: `_data/0001 Deep Dive CQRS.md`

**Uniqueness rule**: `(folder, note_number)` must be unique. Enforced by `_write_lock`.

**Task items** (within task-type notes only):
```
- [ ] Pending task
- [x] Completed task
```
Parsed via regex: `r'^- \[( |x)\] (.+)$'` (multiline).

---

## 2. NoteType

```python
from enum import Enum

class NoteType(str, Enum):
    NOTE    = "note"
    TASK    = "task"
    IDEA    = "idea"
    JOURNAL = "journal"
```

**Detection priority** (highest to lowest):
1. Explicit slash command (`/task`, `/note`, etc.)
2. Inline prefix (`задача:`, `task:`, `todo:`, `нотатка:`, `note:`, `ідея:`, `idea:`, `день:`, `journal:`)
3. AI classification (when no prefix/command)

---

## 3. MoC (Map of Content)

Index note grouping related notes under a topic.

```python
@dataclass
class MoC:
    title: str          # Topic name: "Architecture"
    file_path: str      # Vault-relative: "Architecture/0 Architecture.md"
    children: list[str] # Wikilinks to child notes
    related_mocs: list[str]
```

**File naming**: `0 {TopicName}.md` always at root of its folder.

**MoC file template** (created automatically when new topic first encountered):
```markdown
---
title: "{TopicName}"
date: {today}
categories: [{TopicName}]
tags: [types/moc]
MoC: ""
---

# {TopicName}

## Description

## 🔑 Main sections

## Related MoC

## Additional resources

## Conclusions
```

**MoC update rule**: When a new note is added, append `- [[{note_number:04d} {title}]]`
under `## 🔑 Main sections` in the parent MoC file.

---

## 4. VaultIndex

In-memory snapshot of the full vault state.

```python
@dataclass
class VaultIndex:
    notes: dict[str, VaultNote]         # key: vault-relative file_path
    mocs: dict[str, MoC]                # key: topic name (lowercase)
    topics: list[str]                   # all known topic/folder names
    tags: set[str]                      # all tags across all notes
    total_notes: int
    last_updated: datetime
```

**Build**: Recursive walk of vault directory at startup. Parse YAML frontmatter of each
`.md` file. Estimated time: <15s for 500 notes (SC-004).

**Update**: After every `create_note` call, insert/replace single entry. O(1).

**Rebuild trigger**: Explicit `scan_vault_on_start: true` config flag.

---

## 5. ClassificationResult

Output of `ai/classifier.py` — used internally, not persisted.

```python
@dataclass
class ClassificationResult:
    note_type: NoteType
    topic: str
    folder: str
    parent_moc: str
    title: str
    confidence: float           # 0.0 – 1.0; below 0.5 triggers minimal mode fallback
```

---

## 6. ProcessingMode

```python
class ProcessingMode(str, Enum):
    MINIMAL  = "minimal"    # 0–1 AI calls: classify only (or skip if prefix given)
    BALANCED = "balanced"   # 1–2 AI calls: classify + format
    FULL     = "full"       # 2–3 AI calls: classify + format + enrich (wikilinks)
```

Stored in `config.yaml` under `ai.processing_mode`. Written back on `/mode` command.

---

## 7. AppConfig

Parsed from `config.yaml` at startup. Immutable after load (except `processing_mode`
which is rewritten by `/mode` and requires bot restart to reload).

```python
@dataclass
class AIConfig:
    provider: str               # "anthropic" | "ollama"
    model: str                  # "claude-sonnet-4-6"
    ollama_url: str             # "http://localhost:11434"
    processing_mode: ProcessingMode
    agents_file: str            # ".brain/AGENTS.md"
    skills_path: str            # ".brain/skills/"
    inject_vault_index: bool
    max_context_tokens: int
    api_key: str                # NOT logged, NOT sent to AI

@dataclass
class VaultConfig:
    path: str                   # "C:\SecondaryBrain"
    language: str               # "uk"

@dataclass
class TelegramConfig:
    bot_token: str              # NOT logged
    allowed_user_ids: list[int]

@dataclass
class GitConfig:
    enabled: bool
    auto_commit: bool
    commit_message: str         # "vault: auto-save {date} {time}"
    push_remote: bool
    remote: str
    branch: str
    push_interval_minutes: int

@dataclass
class ScheduleConfig:
    daily_summary_enabled: bool
    daily_summary_time: time    # 21:00
    weekly_review_enabled: bool
    weekly_review_day: str      # "sunday"
    weekly_review_time: time
    monthly_review_enabled: bool
    monthly_review_day: int     # 1-28
    monthly_review_time: time

@dataclass
class AppConfig:
    ai: AIConfig
    vault: VaultConfig
    telegram: TelegramConfig
    git: GitConfig
    schedule: ScheduleConfig
    enrichment_max_related_notes: int
    enrichment_update_moc: bool
    logging_level: str
    logging_log_ai_decisions: bool
    logging_log_path: str
```

---

## 8. SessionStats

In-memory only (not persisted). Reset on bot restart.

```python
@dataclass
class SessionStats:
    tokens_consumed: int        # Accumulated across all AI calls this session
    last_note_path: str         # Last saved vault-relative file path
    notes_saved_today: int      # Count since midnight
    vault_notes_total: int      # From VaultIndex.total_notes
```

Used by `/status` command response.

---

## 9. State Transitions

### Note creation flow:
```
Raw text received
    → Detect type (command / prefix / AI classify)
    → [if balanced/full] AI format
    → [if full] AI enrich (wikilinks)
    → Write file via vault/writer.py
    → Update VaultIndex (in-memory)
    → [if update_moc] Update parent MoC file
    → [if git.enabled] git commit
    → Update SessionStats
    → Send Telegram confirmation
```

### Processing mode lifecycle:
```
Bot starts → load config.yaml → ProcessingMode set
User sends /mode balanced → write config.yaml → confirm to user
→ mode does NOT change until bot restart
→ User restarts bot → new mode loaded from config.yaml
```
