"""search_notes MCP tool handler — zero AI calls.

Uses hybrid BM25+vector search when a VectorStore is available,
otherwise falls back to substring scoring.
"""
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
    vector_store=None,  # VectorStore | None
) -> dict:
    """Search vault notes. Prefers hybrid BM25+vector search; falls back to substring."""
    if vector_store is not None and getattr(vector_store, "is_ready", lambda: False)():
        return _hybrid_search(query, limit, folder, vector_store)
    return _substring_search(query, limit, folder, index, vault_path)


# ── Hybrid search (BM25 + vector via VectorStore.hybrid_search) ───────────────

def _hybrid_search(query: str, limit: int, folder: str | None, vector_store) -> dict:
    results = vector_store.hybrid_search(query, top_k=limit * 2)
    if folder:
        results = [r for r in results if r.file_path.startswith(folder)]
    results = results[:limit]
    return {
        "query": query,
        "total": len(results),
        "mode": "hybrid",
        "results": [
            {
                "file_path": r.file_path,
                "title": r.file_path.rsplit("/", 1)[-1].replace(".md", ""),
                "folder": r.file_path.rsplit("/", 1)[0] if "/" in r.file_path else "",
                "excerpt": r.excerpt,
                "score": r.similarity,
            }
            for r in results
        ],
    }


# ── Substring fallback ────────────────────────────────────────────────────────

def _substring_search(
    query: str, limit: int, folder: str | None, index: VaultIndex, vault_path: str
) -> dict:
    query_lower = query.lower()
    scored: list[tuple[float, dict]] = []

    for path, note in index.notes.items():
        if folder and not path.startswith(folder):
            continue
        score = 0.0
        if query_lower in note.title.lower():
            score += 2.0
        try:
            content = read_note_content(path, vault_path)
        except Exception:
            content = ""
        occurrences = len(re.findall(re.escape(query_lower), content.lower()))
        score += occurrences * 0.5
        if score > 0:
            excerpt = _extract_excerpt(content, query)
            scored.append((score, {
                "file_path": path,
                "title": note.title,
                "folder": note.folder,
                "excerpt": excerpt,
                "score": score,
            }))

    scored.sort(key=lambda x: -x[0])
    results = [r for _, r in scored[:limit]]
    return {"query": query, "total": len(results), "mode": "substring", "results": results}


def _extract_excerpt(content: str, query: str, max_len: int = 120) -> str:
    lower = content.lower()
    idx = lower.find(query.lower())
    if idx == -1:
        return content[:max_len]
    start = max(0, idx - 40)
    end = min(len(content), idx + len(query) + 80)
    return content[start:end].replace("\n", " ")
