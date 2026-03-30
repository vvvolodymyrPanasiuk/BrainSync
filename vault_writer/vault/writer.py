"""Vault writer: sequential note numbering, file creation, MoC updates."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class NoteType(str, Enum):
    NOTE    = "note"
    TASK    = "task"
    IDEA    = "idea"
    JOURNAL = "journal"


@dataclass
class VaultNote:
    title: str
    date: str                        # ISO: YYYY-MM-DD
    categories: list[str]
    tags: list[str]
    moc: str                         # e.g. "[[0 Architecture]]"
    content: str                     # markdown body (after frontmatter)
    file_path: str                   # vault-relative path
    note_type: NoteType
    folder: str                      # vault-relative folder name
    note_number: int                 # sequential number within folder


# ── Thread-safe sequential numbering ─────────────────────────────────────────

_write_lock = threading.Lock()


def next_note_number(folder: Path) -> int:
    """Return next sequential note number within *folder* (caller must hold _write_lock)."""
    existing = [
        f.name for f in folder.glob("*.md")
        if f.name and f.name[0].isdigit()
    ]
    numbers: list[int] = []
    for name in existing:
        prefix = name.split(" ")[0]
        if prefix.isdigit():
            numbers.append(int(prefix))
    return max(numbers, default=0) + 1


def create_folder_if_missing(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)


def write_note(note: VaultNote, vault_path: str) -> str:
    """Write note to vault. Returns vault-relative file path. Thread-safe."""
    with _write_lock:
        vault = Path(vault_path)
        folder = vault / note.folder
        create_folder_if_missing(folder)
        note.note_number = next_note_number(folder)
        filename = f"{note.note_number:04d} {note.title}.md"
        note.file_path = f"{note.folder}/{filename}"
        full_path = folder / filename

        frontmatter = _build_frontmatter(note)
        body = note.content if note.content else _default_body(note)
        full_path.write_text(frontmatter + "\n" + body, encoding="utf-8")
        return note.file_path


def _build_frontmatter(note: VaultNote) -> str:
    import yaml
    data = {
        "title": note.title,
        "date": note.date,
        "categories": note.categories,
        "tags": note.tags,
        "MoC": note.moc,
    }
    return "---\n" + yaml.dump(data, allow_unicode=True, default_flow_style=False).rstrip() + "\n---"


def _default_body(note: VaultNote) -> str:
    return "\n## Description\n\n\n## Conclusions\n\n\n## Links\n\n"


def update_moc(moc_path: str, note_path: str, note_title: str, note_number: int, vault_path: str) -> None:
    """Append wikilink to parent MoC under '## 🔑 Main sections'."""
    full_moc = Path(vault_path) / moc_path
    if not full_moc.exists():
        return
    text = full_moc.read_text(encoding="utf-8")
    link = f"- [[{note_number:04d} {note_title}]]"
    marker = "## 🔑 Main sections"
    if marker in text:
        idx = text.index(marker) + len(marker)
        # Find end of that line, insert after it
        newline_idx = text.find("\n", idx)
        if newline_idx == -1:
            newline_idx = len(text)
        text = text[:newline_idx + 1] + link + "\n" + text[newline_idx + 1:]
    else:
        text += f"\n{marker}\n{link}\n"
    full_moc.write_text(text, encoding="utf-8")


def create_moc_if_missing(topic: str, vault_path: str) -> str:
    """Create MoC file for topic if it doesn't exist. Returns vault-relative path."""
    from datetime import date as _date
    vault = Path(vault_path)
    folder = vault / topic
    create_folder_if_missing(folder)
    moc_file = folder / f"0 {topic}.md"
    vault_rel = f"{topic}/0 {topic}.md"
    if not moc_file.exists():
        today = _date.today().isoformat()
        import yaml
        frontmatter_data = {
            "title": topic,
            "date": today,
            "categories": [topic],
            "tags": ["types/moc"],
            "MoC": "",
        }
        fm = "---\n" + yaml.dump(frontmatter_data, allow_unicode=True, default_flow_style=False).rstrip() + "\n---"
        body = (
            f"\n# {topic}\n\n"
            "## Description\n\n"
            "## 🔑 Main sections\n\n"
            "## Related MoC\n\n"
            "## Additional resources\n\n"
            "## Conclusions\n"
        )
        moc_file.write_text(fm + "\n" + body, encoding="utf-8")
    return vault_rel
