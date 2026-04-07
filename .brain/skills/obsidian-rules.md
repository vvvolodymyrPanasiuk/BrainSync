# Obsidian Rules Skill

## Frontmatter Requirements

Every note MUST have valid YAML frontmatter:
```yaml
---
title: "Note Title"
created: YYYY-MM-DD
aliases:
  - "Note Title"
categories:
  - FolderName
tags:
  - areas/foldername
  - types/notetype
moc: "[[0 FolderName]]"
---
```

- `title`: quoted string
- `created`: ISO format YYYY-MM-DD (NOT `date`)
- `aliases`: list — always include the title so Obsidian resolves `[[Note Title]]` without datetime prefix
- `categories`: list with folder name
- `tags`: list — always include `areas/X` and `types/X` tags
- `moc`: lowercase key, wikilink to parent Map of Content

## Tag Conventions

- `areas/architecture`, `areas/backend`, `areas/frontend` — topic area
- `types/note`, `types/task`, `types/idea`, `types/journal`, `types/moc` — note type
- Tags are always lowercase with hyphens for multi-word: `areas/machine-learning`

## Wikilink Syntax

- Reference notes by title only: `[[Note Title]]` (NO number prefix, NO .md extension)
- Reference MoCs: `[[0 FolderName]]`
- Never use full paths in wikilinks — Obsidian resolves by title via `aliases`
- Aliases allow `[[Note Title]]` to resolve even though the file is `2026-04-06 1423 Note Title.md`

## Sections

Standard note sections (in order):
1. Description — main content
2. Conclusions — key takeaways
3. Links — wikilinks to related notes

Section header names must be translated to the configured locale. Do NOT add extra sections
unless the content genuinely requires it.

## Task Items Format (Obsidian Tasks plugin)

- Pending: `- [ ] Task description`
- Done: `- [x] Task description`
- Place task items directly in the note body (not in frontmatter)
