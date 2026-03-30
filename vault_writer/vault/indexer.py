"""Vault indexer: build and update in-memory VaultIndex."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from vault_writer.vault.reader import read_frontmatter
from vault_writer.vault.writer import NoteType, VaultNote


@dataclass
class VaultIndex:
    notes: dict[str, VaultNote] = field(default_factory=dict)   # key: vault-relative path
    mocs: dict[str, str] = field(default_factory=dict)           # key: topic (lower), val: vault-rel path
    topics: list[str] = field(default_factory=list)
    tags: set[str] = field(default_factory=set)
    total_notes: int = 0
    last_updated: datetime = field(default_factory=datetime.now)


def build_index(vault_path: str) -> VaultIndex:
    """Walk vault directory, parse frontmatter of every .md, return VaultIndex."""
    index = VaultIndex()
    vault = Path(vault_path)
    if not vault.is_dir():
        return index

    for md_file in vault.rglob("*.md"):
        rel = md_file.relative_to(vault).as_posix()
        try:
            fm = read_frontmatter(str(md_file))
        except Exception:
            continue

        note_type_str = fm.get("type", "note")
        try:
            note_type = NoteType(note_type_str)
        except ValueError:
            note_type = NoteType.NOTE

        name = md_file.name
        folder = md_file.parent.relative_to(vault).as_posix() if md_file.parent != vault else ""

        # Detect MoC files (named "0 *.md")
        if name.startswith("0 ") and name.endswith(".md"):
            topic = name[2:-3]  # strip "0 " prefix and ".md"
            index.mocs[topic.lower()] = rel
            index.topics.append(topic)
            continue

        note_number = 0
        prefix = name.split(" ")[0]
        if prefix.isdigit():
            note_number = int(prefix)

        title = fm.get("title", name[:-3])
        tags = fm.get("tags", []) or []
        note = VaultNote(
            title=title,
            date=str(fm.get("date", "")),
            categories=fm.get("categories", []) or [],
            tags=tags if isinstance(tags, list) else [tags],
            moc=fm.get("MoC", ""),
            content="",   # not loaded into index — read on demand
            file_path=rel,
            note_type=note_type,
            folder=folder,
            note_number=note_number,
        )
        index.notes[rel] = note
        for tag in note.tags:
            index.tags.add(tag)

    index.total_notes = len(index.notes)
    # De-duplicate and sort topics
    index.topics = sorted(set(index.topics))
    index.last_updated = datetime.now()
    return index


def update_index(index: VaultIndex, note: VaultNote) -> None:
    """Insert/replace single note in index. O(1)."""
    index.notes[note.file_path] = note
    for tag in note.tags:
        index.tags.add(tag)
    if note.folder and note.folder not in index.topics:
        index.topics.append(note.folder)
        index.topics.sort()
    index.total_notes = len(index.notes)
    index.last_updated = datetime.now()
