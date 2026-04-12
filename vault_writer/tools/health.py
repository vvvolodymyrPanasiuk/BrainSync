"""Vault health check: orphan notes, broken wikilinks, missing aliases, duplicate titles,
isolated notes, topics without MoC, stale notes (LLM-Wiki lint pattern)."""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path


_LINK_PAT = re.compile(r'\[\[([^\]|#]+)(?:[|#][^\]]+)?\]\]')

# Notes older than this (days) are flagged as potentially stale
_STALENESS_DAYS_DEFAULT = 180


def run_health_check(vault_path: str, index, provider=None, staleness_days: int = _STALENESS_DAYS_DEFAULT) -> dict:
    """Scan vault and return a health report dict.

    Returns:
        orphans:      notes with no incoming [[wikilinks]] from other notes
        broken_links: [[links]] that don't resolve to any existing note title
        no_aliases:   notes whose frontmatter has no aliases: field
        duplicates:   (title, [path, ...]) pairs with identical titles
        isolated:     notes with no outgoing [[wikilinks]]
        topics_no_moc: top-level folders missing a MoC file
        stale:        notes created > staleness_days ago (potentially outdated)
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

    # Orphans: note whose title was never referenced by any other note
    orphans = [
        path for path, note in index.notes.items()
        if note.title.lower().strip() not in referenced
    ]

    # Duplicate titles
    counts: dict[str, list[str]] = {}
    for path, note in index.notes.items():
        counts.setdefault(note.title.lower().strip(), []).append(path)
    duplicates = [(t, paths) for t, paths in counts.items() if len(paths) > 1]

    # Isolated: notes with no outgoing [[wikilinks]]
    isolated: list[str] = []
    for path in index.notes:
        fp = vault / path
        if not fp.exists():
            continue
        try:
            if "[[" not in fp.read_text(encoding="utf-8", errors="replace"):
                isolated.append(path)
        except Exception:
            pass

    # Topics (top-level folders) missing a MoC file
    top_folders: set[str] = set()
    for note in index.notes.values():
        top = note.folder.split("/")[0] if note.folder else ""
        if top:
            top_folders.add(top)
    topics_no_moc = [
        f for f in sorted(top_folders)
        if not (vault / f / f"0 {f}.md").exists() and not (vault / f"{f}.md").exists()
    ]

    # Stale notes: created more than staleness_days ago
    cutoff = date.today() - timedelta(days=staleness_days)
    stale: list[str] = []
    for path, note in index.notes.items():
        try:
            if date.fromisoformat(note.date) < cutoff:
                stale.append(path)
        except Exception:
            continue

    return {
        "orphans": orphans,
        "broken_links": broken,
        "no_aliases": no_aliases,
        "duplicates": duplicates,
        "isolated": isolated,
        "topics_no_moc": topics_no_moc,
        "stale": stale,
        "total": index.total_notes,
    }
