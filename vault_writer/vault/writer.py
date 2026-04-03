"""Vault writer: sequential note numbering, file creation, MoC updates."""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

# Characters forbidden in Windows filenames
_WIN_FORBIDDEN = str.maketrans({c: "" for c in r'\/:*?"<>|'})

# Sub-folder where notes are stored inside each topic folder
DATA_SUBFOLDER = "_data"


def _sanitize_filename(title: str, max_len: int = 80) -> str:
    """Remove Windows-forbidden characters and trim to max_len."""
    clean = title.translate(_WIN_FORBIDDEN).strip()
    # Collapse multiple spaces/dots
    while "  " in clean:
        clean = clean.replace("  ", " ")
    clean = clean.strip(". ")
    return clean[:max_len] if clean else "note"


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
    folder: str                      # vault-relative folder name (topic)
    note_number: int                 # sequential number within _data/
    use_data_subfolder: bool = True  # write to folder/_data/ (new structure)


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


def _assert_within_vault(path: Path, vault: Path, label: str) -> None:
    """Raise ValueError if *path* resolves outside *vault* (prevents path traversal)."""
    try:
        path.resolve().relative_to(vault.resolve())
    except ValueError:
        raise ValueError(f"Path traversal blocked: {label!r} escapes vault boundary")


def write_note(note: VaultNote, vault_path: str) -> str:
    """Write note to vault. Returns vault-relative file path. Thread-safe.

    New structure (use_data_subfolder=True):
        Topic/_data/0001 Title.md
    Legacy structure (use_data_subfolder=False):
        Topic/0001 Title.md
    """
    with _write_lock:
        vault = Path(vault_path)
        topic_folder = vault / note.folder
        _assert_within_vault(topic_folder, vault, note.folder)
        create_folder_if_missing(topic_folder)

        # Determine target folder for the note file
        if note.use_data_subfolder:
            data_folder = topic_folder / DATA_SUBFOLDER
            create_folder_if_missing(data_folder)
            rel_data = f"{note.folder}/{DATA_SUBFOLDER}"
        else:
            data_folder = topic_folder
            rel_data = note.folder

        note.note_number = next_note_number(data_folder)
        safe_title = _sanitize_filename(note.title)
        filename = f"{note.note_number:04d} {safe_title}.md"
        note.file_path = f"{rel_data}/{filename}"
        full_path = data_folder / filename
        _assert_within_vault(full_path, vault, note.file_path)

        frontmatter = _build_frontmatter(note)
        body = note.content if note.content else _default_body(note)
        full_path.write_text(frontmatter + "\n" + body, encoding="utf-8")
        logger.info("write_note: %s", note.file_path)
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
    vault = Path(vault_path)
    full_moc = vault / moc_path
    _assert_within_vault(full_moc, vault, moc_path)
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


def create_mocs_for_path(full_folder: str, vault_path: str) -> str:
    """Create MOC files at every level of full_folder and link child MOCs in parent.
    Returns vault-relative path of the innermost (most specific) MOC."""
    parts = [p for p in full_folder.split("/") if p]
    moc_paths: list[tuple[str, str]] = []  # (folder_name, moc_rel_path)

    for i in range(len(parts)):
        partial = "/".join(parts[: i + 1])
        moc_rel = create_moc_if_missing(partial, vault_path)
        moc_paths.append((parts[i], moc_rel))

    # Link each child MOC in its parent's "Related MoC" section
    for i in range(1, len(moc_paths)):
        child_name, _child_moc = moc_paths[i]
        _parent_name, parent_moc = moc_paths[i - 1]
        _link_child_moc_in_parent(parent_moc, child_name, vault_path)

    return moc_paths[-1][1] if moc_paths else ""


def _link_child_moc_in_parent(parent_moc_path: str, child_name: str, vault_path: str) -> None:
    """Append wikilink to child folder MOC under parent's 'Related MoC' section (idempotent)."""
    vault = Path(vault_path)
    full_moc = vault / parent_moc_path
    if not full_moc.exists():
        return
    text = full_moc.read_text(encoding="utf-8")
    link = f"- [[0 {child_name}]]"
    if link in text:
        return
    marker = "## Related MoC"
    if marker in text:
        idx = text.index(marker) + len(marker)
        newline_idx = text.find("\n", idx)
        if newline_idx == -1:
            newline_idx = len(text)
        text = text[: newline_idx + 1] + link + "\n" + text[newline_idx + 1 :]
    else:
        text += f"\n{marker}\n{link}\n"
    full_moc.write_text(text, encoding="utf-8")


def create_moc_if_missing(topic: str, vault_path: str) -> str:
    """Create MoC file for topic (may be a nested path like 'Навчання/Програмування').
    File is named after the last path component. Returns vault-relative path."""
    from datetime import date as _date
    vault = Path(vault_path)
    folder = vault / topic
    _assert_within_vault(folder, vault, topic)
    create_folder_if_missing(folder)
    # Use only the last component as the MOC filename (safe on all OSes)
    folder_name = topic.split("/")[-1] if "/" in topic else topic
    moc_file = folder / f"0 {folder_name}.md"
    vault_rel = f"{topic}/0 {folder_name}.md"
    if not moc_file.exists():
        today = _date.today().isoformat()
        import yaml
        frontmatter_data = {
            "title": folder_name,
            "date": today,
            "categories": [folder_name],
            "tags": ["types/moc"],
            "MoC": "",
        }
        fm = "---\n" + yaml.dump(frontmatter_data, allow_unicode=True, default_flow_style=False).rstrip() + "\n---"
        body = (
            f"\n# {folder_name}\n\n"
            "## Description\n\n"
            "## 🔑 Main sections\n\n"
            "## Related MoC\n\n"
            "## Additional resources\n\n"
            "## Conclusions\n"
        )
        moc_file.write_text(fm + "\n" + body, encoding="utf-8")
    return vault_rel
