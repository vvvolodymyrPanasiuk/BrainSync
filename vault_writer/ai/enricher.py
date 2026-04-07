"""AI enricher: add wikilinks to note content in full processing mode."""
from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Common Ukrainian and English stop words to skip during keyword overlap scoring
_STOP_WORDS: frozenset[str] = frozenset({
    # Ukrainian
    "і", "й", "в", "у", "на", "з", "із", "зі", "що", "як", "до", "це",
    "не", "але", "або", "про", "від", "для", "по", "при", "та", "також",
    "тому", "якщо", "вже", "так", "а", "є", "був", "була", "було", "були",
    "де", "хто", "ти", "я", "ми", "він", "вона", "воно", "вони", "яка",
    "який", "яке", "які", "той", "та", "те", "ті", "цей", "ця", "ці",
    "його", "її", "їх", "нас", "вас", "нам", "вам", "ним", "ній",
    "коли", "тільки", "навіть", "між", "через", "після", "перед", "над",
    "під", "без", "крім", "щоб", "чи", "бо", "хоча", "поки", "потім",
    # English
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
    "for", "of", "with", "by", "from", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "that", "this",
    "it", "its", "not", "as", "if", "so", "then", "than", "when",
})


def add_wikilinks(text: str, vault_index, config) -> str:
    """Scan vault index for related notes and inject wikilinks. Full mode only (FR-011).

    Finds top N related notes by topic/tag overlap, appends them to ## Посилання section.
    Returns enriched content string.
    """
    from vault_writer.vault.indexer import VaultIndex
    index: VaultIndex = vault_index
    max_related = config.enrichment_max_related_notes

    if not index.notes:
        return text

    # Keywords: strip stop words and short tokens for better signal
    words = {
        w for w in re.findall(r"\w+", text.lower())
        if w not in _STOP_WORDS and len(w) > 2
    }
    scored: list[tuple[float, str, str]] = []  # (score, file_path, title)
    for fp, note in index.notes.items():
        note_words = {
            w for w in re.findall(r"\w+", note.title.lower())
            if w not in _STOP_WORDS and len(w) > 2
        }
        note_words |= {t.split("/")[-1].lower() for t in note.tags}
        overlap = len(words & note_words)
        if overlap > 0:
            scored.append((overlap, fp, note.title))

    scored.sort(key=lambda x: -x[0])
    top = scored[:max_related]

    if not top:
        return text

    # Wikilink uses filename stem (works for both old 0001-style and new date-style names)
    links = "\n".join(
        f"- [[{Path(fp).stem}]]"
        for _, fp, _ in top
    )

    links_section = "## Посилання"
    if links_section in text:
        idx = text.index(links_section) + len(links_section)
        newline_idx = text.find("\n", idx)
        if newline_idx == -1:
            return text + "\n" + links
        return text[:newline_idx + 1] + links + "\n" + text[newline_idx + 1:]
    else:
        return text + f"\n\n{links_section}\n\n{links}\n"
