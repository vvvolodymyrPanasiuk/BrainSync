# Obsidian Rules Skill

## Frontmatter Requirements

Every note MUST have valid YAML frontmatter:
```yaml
---
title: "Note Title"
date: YYYY-MM-DD
categories: [FolderName]
tags: [areas/foldername, types/notetype]
MoC: "[[0 FolderName]]"
---
```

- `title`: quoted string
- `date`: ISO format YYYY-MM-DD
- `categories`: list with single folder name
- `tags`: list — always include `areas/X` and `types/X` tags
- `MoC`: wikilink to parent Map of Content

## Tag Conventions

- `areas/architecture`, `areas/backend`, `areas/frontend` — topic area
- `types/notes`, `types/task`, `types/idea`, `types/journal`, `types/moc` — note type
- Tags are always lowercase with hyphens for multi-word: `areas/machine-learning`

## Wikilink Syntax

- Reference notes: `[[0004 CQRS патерн]]` (number + space + title, no .md extension)
- Reference MoCs: `[[0 Architecture]]`
- Never use full paths in wikilinks — Obsidian resolves by filename

## Sections

Standard note sections (in order):
1. `## Description` — main content
2. `## Conclusions` — key takeaways
3. `## Links` — wikilinks to related notes

Do NOT add extra sections unless the content genuinely requires it.

## Task Items Format (Obsidian Tasks plugin)

- Pending: `- [ ] Task description`
- Done: `- [x] Task description`
- Place task items directly in the note body (not in frontmatter)
