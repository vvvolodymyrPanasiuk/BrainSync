# VaultWriter Skill: Folder Naming and Note Structure

## Folder Naming Conventions

- Use PascalCase for folder names (e.g. `Learning`, `Programming`, `Trading`, `Business`)
- Folder path has up to 4 levels: `GeneralCategory/Topic/Subtopic/Section`
- Match the topic name exactly as it appears in existing MoC files
- If no existing folder matches, create a new one with PascalCase name

## File Naming

- Files are named by datetime: `YYYY-MM-DD HHmm Title.md`
- MoC files always use prefix `0`: `0 TopicName.md`
- Never use sequential numbers for regular notes

## MoC Update Rules

When creating a note:
1. Find or create the parent MoC file (`0 {FolderName}.md`)
2. Append `- [[Note Title]]` under the main sections heading
3. One entry per note — do not duplicate
4. Wikilinks use the note title only — Obsidian resolves via `aliases` frontmatter

## Note Template

Write content in the configured locale. Section header names must be translated to the locale.

```markdown
---
title: "{Title}"
created: YYYY-MM-DD
aliases:
  - "{Title}"
categories:
  - FolderName
tags:
  - areas/foldername
  - types/notetype
moc: "[[0 FolderName]]"
---

## <Description heading in locale>

{Expanded description of the concept}

## <Conclusions heading in locale>

{Key takeaway, action item, or implication}

## <Links heading in locale>

- [[Related Note Title]]
```
