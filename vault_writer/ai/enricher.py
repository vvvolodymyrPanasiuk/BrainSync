"""AI enricher: add wikilinks to note content in full processing mode."""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


def add_wikilinks(text: str, vault_index, config) -> str:
    """Scan vault index for related notes and inject wikilinks. Full mode only (FR-011).

    Finds top N related notes by topic/tag overlap, appends them to ## Links section.
    Returns enriched content string.
    """
    from vault_writer.vault.indexer import VaultIndex
    index: VaultIndex = vault_index
    max_related = config.enrichment_max_related_notes

    if not index.notes:
        return text

    # Collect candidate notes by simple keyword overlap with existing note titles/tags
    words = set(re.findall(r"\w+", text.lower()))
    scored: list[tuple[float, str, str]] = []  # (score, file_path, title)
    for path, note in index.notes.items():
        note_words = set(re.findall(r"\w+", note.title.lower()))
        note_words |= {t.split("/")[-1].lower() for t in note.tags}
        overlap = len(words & note_words)
        if overlap > 0:
            scored.append((overlap, path, note.title))

    scored.sort(key=lambda x: -x[0])
    top = scored[:max_related]

    if not top:
        return text

    links = "\n".join(
        f"- [[{note_number_from_path(fp)} {title}]]"
        for _, fp, title in top
    )

    links_section = "## Links"
    if links_section in text:
        # Append after existing links section header
        idx = text.index(links_section) + len(links_section)
        newline_idx = text.find("\n", idx)
        if newline_idx == -1:
            return text + "\n" + links
        return text[:newline_idx + 1] + links + "\n" + text[newline_idx + 1:]
    else:
        return text + f"\n\n{links_section}\n\n{links}\n"


def note_number_from_path(file_path: str) -> str:
    """Extract NNNN prefix from file path for wikilink formatting."""
    name = file_path.split("/")[-1]
    prefix = name.split(" ")[0]
    if prefix.isdigit():
        return f"{int(prefix):04d}"
    return ""
