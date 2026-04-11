"""BM25 full-text index for vault notes.

Wraps rank-bm25's BM25Okapi with an in-memory corpus that stays in sync
with the vector store:  build() at startup, upsert() on every note save.
Falls back silently if rank-bm25 is not installed.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    """Whitespace + punctuation tokenizer, lowercased."""
    return re.findall(r"\w+", text.lower())


class BM25Index:
    def __init__(self) -> None:
        self._bm25 = None
        self._paths: list[str] = []
        self._corpus: list[list[str]] = []
        self._excerpts: dict[str, str] = {}
        self._path_to_idx: dict[str, int] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def build(self, vault_path: str) -> int:
        """Scan all .md files in vault and build the BM25 index from scratch.

        Called at startup and on /reindex.  Returns number of notes indexed.
        """
        if not self._bm25_available():
            return 0

        vault = Path(vault_path)
        corpus: list[list[str]] = []
        paths: list[str] = []
        excerpts: dict[str, str] = {}

        for md_file in sorted(vault.rglob("*.md")):
            if md_file.name.startswith("0 "):
                continue
            try:
                content = md_file.read_text(encoding="utf-8", errors="replace")
                if not content.strip():
                    continue
                rel = str(md_file.relative_to(vault))
                corpus.append(_tokenize(content))
                paths.append(rel)
                excerpts[rel] = content[:300].replace("\n", " ")
            except Exception as exc:
                logger.warning("BM25Index.build: skip %s: %s", md_file, exc)

        self._paths = paths
        self._corpus = corpus
        self._excerpts = excerpts
        self._path_to_idx = {p: i for i, p in enumerate(paths)}
        self._rebuild()
        logger.info("BM25Index built: %d notes", len(paths))
        return len(paths)

    def upsert(self, path: str, content: str) -> None:
        """Add or update a single document and rebuild the in-memory BM25 model."""
        if not self._bm25_available():
            return
        tokens = _tokenize(content)
        excerpt = content[:300].replace("\n", " ")
        if path in self._path_to_idx:
            idx = self._path_to_idx[path]
            self._corpus[idx] = tokens
            self._excerpts[path] = excerpt
        else:
            self._path_to_idx[path] = len(self._paths)
            self._paths.append(path)
            self._corpus.append(tokens)
            self._excerpts[path] = excerpt
        self._rebuild()

    def delete(self, path: str) -> None:
        """Remove a document and rebuild."""
        if path not in self._path_to_idx:
            return
        idx = self._path_to_idx.pop(path)
        self._paths.pop(idx)
        self._corpus.pop(idx)
        self._excerpts.pop(path, None)
        # Re-index remaining paths
        self._path_to_idx = {p: i for i, p in enumerate(self._paths)}
        self._rebuild()

    def search(self, query: str, top_k: int) -> list[tuple[str, float, str]]:
        """Return up to top_k results as (path, bm25_score, excerpt) tuples."""
        if self._bm25 is None or not self._paths:
            return []
        tokens = _tokenize(query)
        raw_scores = self._bm25.get_scores(tokens)
        ranked = sorted(range(len(raw_scores)), key=lambda i: -raw_scores[i])
        results: list[tuple[str, float, str]] = []
        for i in ranked[:top_k]:
            if raw_scores[i] <= 0:
                break
            path = self._paths[i]
            results.append((path, float(raw_scores[i]), self._excerpts.get(path, "")))
        return results

    @property
    def is_ready(self) -> bool:
        return self._bm25 is not None and bool(self._paths)

    # ── Internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _bm25_available() -> bool:
        try:
            import rank_bm25  # noqa: F401
            return True
        except ImportError:
            logger.debug("rank-bm25 not installed — BM25 index disabled")
            return False

    def _rebuild(self) -> None:
        if not self._corpus:
            self._bm25 = None
            return
        try:
            from rank_bm25 import BM25Okapi
            self._bm25 = BM25Okapi(self._corpus)
        except Exception as exc:
            logger.warning("BM25Index._rebuild failed: %s", exc)
            self._bm25 = None
