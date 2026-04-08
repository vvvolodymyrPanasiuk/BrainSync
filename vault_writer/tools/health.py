"""Vault health check: orphan notes, broken wikilinks, missing aliases, duplicate titles."""
from __future__ import annotations

import re
from pathlib import Path


_LINK_PAT = re.compile(r'\[\[([^\]|#]+)(?:[|#][^\]]+)?\]\]')


def run_health_check(vault_path: str, index) -> dict:
    """Scan vault and return a health report dict.

    Returns:
        orphans:      notes with no incoming [[wikilinks]] from other notes
        broken_links: [[links]] that don't match any existing note title
        no_aliases:   notes whose frontmatter has no aliases: field
        duplicates:   (title, [path, ...]) pairs with identical titles
        total:        total notes scanned
    """
    vault = Path(vault_path)

    # Build lowercase title → path map for fast lookup
    title_to_path: dict[str, str] = {}
    for path, note in index.notes.items():
        key = note.title.lower().strip()
        if key not in title_to_path:
            title_to_path[key] = path

    referenced: set[str] = set()   # lowercase titles referenced by any note
    broken: list[dict] = []
    no_aliases: list[str] = []

    for note_path, note in index.notes.items():
        fp = vault / note_path
        if not fp.exists():
            continue
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            continue

        # Check for aliases: field in frontmatter
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1 and "aliases:" not in content[3:end]:
                no_aliases.append(note_path)

        # Collect all outgoing wikilinks
        for m in _LINK_PAT.finditer(content):
            ref = m.group(1).strip()
            ref_lower = ref.lower()
            referenced.add(ref_lower)
            if ref_lower not in title_to_path:
                broken.append({"note": note_path, "link": ref})

    # Orphans: note whose title was never referenced
    orphans = [
        path for path, note in index.notes.items()
        if note.title.lower().strip() not in referenced
    ]

    # Duplicate titles
    counts: dict[str, list[str]] = {}
    for path, note in index.notes.items():
        counts.setdefault(note.title.lower().strip(), []).append(path)
    duplicates = [(t, paths) for t, paths in counts.items() if len(paths) > 1]

    return {
        "orphans": orphans,
        "broken_links": broken,
        "no_aliases": no_aliases,
        "duplicates": duplicates,
        "total": index.total_notes,
    }
