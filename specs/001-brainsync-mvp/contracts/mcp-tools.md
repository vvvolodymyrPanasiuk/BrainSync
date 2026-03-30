# MCP Tool Contracts: VaultWriter

**Branch**: `001-brainsync-mvp` | **Date**: 2026-03-30
**Server name**: `vault-writer`
**Transport**: stdio (for Claude Code registration)

---

## Tool: create_note

Creates a new structured note in the Obsidian vault.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "text": {
      "type": "string",
      "description": "Raw input text to save as a note"
    },
    "type": {
      "type": "string",
      "enum": ["note", "task", "idea", "journal"],
      "description": "Optional explicit note type override. If omitted, AI classification is used."
    },
    "folder": {
      "type": "string",
      "description": "Optional vault-relative folder override (e.g. 'Architecture'). If omitted, AI determines folder."
    }
  },
  "required": ["text"]
}
```

### Output Schema

```json
{
  "success": true,
  "file_path": "Architecture/0004 CQRS патерн.md",
  "title": "CQRS патерн",
  "parent_moc": "Architecture/0 Architecture.md",
  "ai_calls_made": 2
}
```

### Error response

```json
{
  "success": false,
  "error": "Vault path not found: C:\\SecondaryBrain",
  "file_path": null
}
```

### Behaviour

- If `type` is provided → skip AI classification (0 calls for classification step)
- If `folder` is provided → skip folder selection AI call
- Processing mode from `config.yaml` controls formatting/enrichment steps
- Triggers MoC update if `enrichment.update_moc: true`
- Triggers git commit if `git.enabled: true` and `git.auto_commit: true`

---

## Tool: search_notes

Full-text search across the vault.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Search query string"
    },
    "limit": {
      "type": "integer",
      "default": 10,
      "description": "Maximum number of results to return"
    },
    "folder": {
      "type": "string",
      "description": "Optional vault-relative folder to scope the search"
    }
  },
  "required": ["query"]
}
```

### Output Schema

```json
{
  "results": [
    {
      "file_path": "Architecture/0004 CQRS патерн.md",
      "title": "CQRS патерн",
      "excerpt": "...CQRS розділяє read і write моделі...",
      "score": 0.92
    }
  ],
  "total_found": 3
}
```

### Behaviour

- Search is case-insensitive substring match across title + content body
- `score` is a simple TF-based relevance float (0.0–1.0); no AI used
- Zero AI calls

---

## Tool: update_moc

Adds a wikilink to an existing MoC file.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "moc_path": {
      "type": "string",
      "description": "Vault-relative path to the MoC file"
    },
    "note_path": {
      "type": "string",
      "description": "Vault-relative path to the note being linked"
    },
    "note_title": {
      "type": "string",
      "description": "Display title for the wikilink"
    }
  },
  "required": ["moc_path", "note_path", "note_title"]
}
```

### Output Schema

```json
{
  "success": true
}
```

---

## Tool: classify_content

Classifies raw text and returns structured metadata without saving.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "text": {
      "type": "string",
      "description": "Raw text to classify"
    }
  },
  "required": ["text"]
}
```

### Output Schema

```json
{
  "type": "note",
  "topic": "Architecture",
  "folder": "Architecture",
  "parent_moc": "Architecture/0 Architecture.md",
  "title": "CQRS патерн",
  "confidence": 0.87
}
```

### Behaviour

- Always makes exactly 1 AI call
- Confidence < 0.5 → caller should treat result as uncertain

---

## Tool: get_vault_index

Returns the current in-memory vault index snapshot.

### Input Schema

```json
{}
```

### Output Schema

```json
{
  "total_notes": 47,
  "mocs": [
    {
      "path": "Architecture/0 Architecture.md",
      "title": "Architecture",
      "children": ["Architecture/0004 CQRS патерн.md"]
    }
  ],
  "topics": ["Architecture", "Health", "Business"],
  "last_updated": "2026-03-30T21:15:00"
}
```

### Behaviour

- Zero AI calls
- Returns snapshot of in-memory VaultIndex; may be up to 1 write behind
