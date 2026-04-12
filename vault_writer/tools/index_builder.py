"""Global vault/index.md catalog builder — LLM-Wiki pattern.

Rebuilds a human- and AI-readable catalog of every note in the vault,
organized by top-level folder (MoC hierarchy).  Used by:
  - /reindex command
  - weekly scheduled job
  - post-ingest background task (async)
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def rebuild_index_md(vault_path: str, vault_index) -> str:
    """Write vault/index.md — global content-oriented catalog.

    Each entry: [[Note Title]] — YYYY-MM-DD — first meaningful sentence.
    Notes are grouped by top-level folder and sorted newest-first.

    Returns the vault-relative path ('index.md').
    """
    vault = Path(vault_path)

    # Group notes by top-level folder
    by_folder: dict[str, list] = defaultdict(list)
    for path, note in vault_index.notes.items():
        top = note.folder.split("/")[0] if note.folder else "General"
        by_folder[top].append((path, note))

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = vault_index.total_notes

    lines: list[str] = [
        "# Vault Index",
        "",
        f"> Auto-generated: {now} · {total} notes",
        "> Do not edit manually — this file is rebuilt by BrainSync.",
        "",
    ]

    for folder in sorted(by_folder.keys()):
        entries = sorted(by_folder[folder], key=lambda x: x[1].date or "", reverse=True)
        lines.append(f"## {folder}  ({len(entries)})")
        lines.append("")

        for note_path, note in entries:
            summary = _extract_first_line(vault / note_path)
            title = note.title or Path(note_path).stem
            date_str = note.date or ""
            line = f"- [[{title}]] — {date_str}"
            if summary:
                line += f" — {summary}"
            lines.append(line)

        lines.append("")

    content = "\n".join(lines)
    index_path = vault / "index.md"
    try:
        index_path.write_text(content, encoding="utf-8")
        logger.info("index_builder: wrote index.md (%d notes, %d folders)", total, len(by_folder))
    except Exception as exc:
        logger.error("index_builder: write failed: %s", exc)

    return "index.md"


def _extract_first_line(note_path: Path) -> str:
    """Return the first meaningful prose line from a note (after frontmatter + headings)."""
    if not note_path.exists():
        return ""
    try:
        content = note_path.read_text(encoding="utf-8", errors="replace")
        # Strip YAML frontmatter
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                content = content[end + 3:]
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("!") and len(line) > 20:
                return line[:120]
    except Exception:
        pass
    return ""
