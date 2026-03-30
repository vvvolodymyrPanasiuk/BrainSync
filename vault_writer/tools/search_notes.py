"""search_notes MCP tool handler — zero AI calls."""
from __future__ import annotations

import re

from vault_writer.vault.indexer import VaultIndex
from vault_writer.vault.reader import read_note_content


def handle_search_notes(
    query: str,
    limit: int,
    folder: str | None,
    index: VaultIndex,
    vault_path: str,
) -> dict:
    """Case-insensitive substring search across title + content. Returns sorted results."""
    query_lower = query.lower()
    scored: list[tuple[float, dict]] = []

    for path, note in index.notes.items():
        if folder and not path.startswith(folder):
            continue
        title_lower = note.title.lower()
        # TF score: title match weighs more
        score = 0.0
        if query_lower in title_lower:
            score += 2.0

        try:
            content = read_note_content(path, vault_path)
        except Exception:
            content = ""

        content_lower = content.lower()
        occurrences = len(re.findall(re.escape(query_lower), content_lower))
        score += occurrences * 0.5

        if score > 0:
            excerpt = _extract_excerpt(content, query, max_len=120)
            scored.append((score, {
                "file_path": path,
                "title": note.title,
                "folder": note.folder,
                "excerpt": excerpt,
                "score": score,
            }))

    scored.sort(key=lambda x: -x[0])
    results = [r for _, r in scored[:limit]]
    return {"query": query, "total": len(results), "results": results}


def _extract_excerpt(content: str, query: str, max_len: int = 120) -> str:
    lower = content.lower()
    idx = lower.find(query.lower())
    if idx == -1:
        return content[:max_len]
    start = max(0, idx - 40)
    end = min(len(content), idx + len(query) + 80)
    return content[start:end].replace("\n", " ")
