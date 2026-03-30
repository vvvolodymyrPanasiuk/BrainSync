# VaultWriter Skill: Folder Naming and Note Structure

## Folder Naming Conventions

- Use PascalCase for folder names: `Architecture`, `Backend`, `Frontend`, `Tasks`, `Ideas`, `Journal`
- Match the topic name exactly as it appears in existing MoC files
- If no existing folder matches, create a new one with PascalCase name
- Common folders: `Architecture`, `Backend`, `Frontend`, `DevOps`, `Learning`, `Tasks`, `Ideas`,
  `Journal`, `Research`, `General`

## Sequential Numbering

- Files are named `NNNN Title.md` where NNNN is 4-digit zero-padded
- Numbers are sequential within each folder, starting at 0001
- MoC files always use prefix `0`: `0 Architecture.md`
- Never reuse or skip numbers

## MoC Update Rules

When creating a note:
1. Find or create the parent MoC file (`0 {Folder}.md`)
2. Append `- [[NNNN Title]]` under `## 🔑 Main sections`
3. One entry per note — do not duplicate

## Note Template

```markdown
---
title: "{Title}"
date: YYYY-MM-DD
categories: [FolderName]
tags: [areas/foldername, types/notetype]
MoC: "[[0 FolderName]]"
---

## Description

{Expanded description of the concept}

## Conclusions

{Key takeaway, action item, or implication}

## Links

- [[NNNN Related Note]]
```
