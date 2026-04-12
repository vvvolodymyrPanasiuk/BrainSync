"""VectorStore: ChromaDB wrapper for vault note embeddings + BM25 hybrid search."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from vault_writer.rag.embedder import EmbeddingProvider
from vault_writer.rag.engine import SearchResult, SimilarityNotice

logger = logging.getLogger(__name__)

_COLLECTION_NAME  = "vault_notes"
_RRF_K            = 60    # standard RRF constant
_CHUNK_THRESHOLD  = 1500  # chars: docs longer than this get split
_CHUNK_SIZE       = 600   # chars per chunk
_CHUNK_OVERLAP    = 100   # chars overlap between adjacent chunks
_CHUNK_SEP        = "::chunk_"


def _split_chunks(content: str) -> list[str]:
    chunks, start = [], 0
    while start < len(content):
        end = min(start + _CHUNK_SIZE, len(content))
        chunks.append(content[start:end])
        if end == len(content):
            break
        start = end - _CHUNK_OVERLAP
    return chunks


def _parent_path(doc_id: str) -> str:
    """Return original file path, stripping ::chunk_N suffix if present."""
    return doc_id.split(_CHUNK_SEP)[0] if _CHUNK_SEP in doc_id else doc_id


class VectorStore:
    def __init__(self, index_path: str, embedder: EmbeddingProvider) -> None:
        import chromadb
        from vault_writer.rag.bm25_index import BM25Index
        self._embedder = embedder
        self._building = False
        self._bm25 = BM25Index()
        client = chromadb.PersistentClient(path=index_path)
        self._collection = client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        count = self._collection.count()
        if count > 0:
            logger.info("VectorStore loaded existing index: %d notes", count)
        else:
            logger.info("VectorStore initialised empty index at %s", index_path)

    def upsert_note(self, file_path: str, content: str) -> None:
        """Embed and upsert a note. Long docs are split into overlapping chunks."""
        # BM25 always indexes the full document
        self._bm25.upsert(file_path, content)

        if len(content) <= _CHUNK_THRESHOLD:
            self._upsert_single(file_path, content, file_path)
        else:
            # Remove any previous entries for this path, then index chunks
            self._delete_from_collection(file_path)
            for i, chunk in enumerate(_split_chunks(content)):
                self._upsert_single(f"{file_path}{_CHUNK_SEP}{i}", chunk, file_path)
            logger.debug("upsert_note: %s → %d chunks", file_path, len(_split_chunks(content)))

    def _upsert_single(self, doc_id: str, content: str, path: str) -> None:
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        existing = self._collection.get(ids=[doc_id], include=["metadatas"])
        if existing["ids"] and existing["metadatas"][0].get("hash") == content_hash:
            return
        self._collection.upsert(
            ids=[doc_id],
            embeddings=self._embedder.embed([content]),
            documents=[content],
            metadatas=[{"hash": content_hash, "path": path}],
        )

    def _delete_from_collection(self, file_path: str) -> None:
        """Delete the whole-doc entry AND any chunk entries for file_path."""
        try:
            res = self._collection.get(where={"path": file_path}, include=[])
            if res["ids"]:
                self._collection.delete(ids=res["ids"])
        except Exception:
            pass

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        """Semantic search. Chunks are deduplicated to parent paths."""
        total = self._collection.count()
        if total == 0:
            return []
        embeddings = self._embedder.embed([query])
        # Fetch more than top_k so deduplication doesn't starve results
        n = min(top_k * 4, total)
        results = self._collection.query(
            query_embeddings=embeddings,
            n_results=n,
            include=["documents", "metadatas", "distances"],
        )
        ids       = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]
        # Keep best chunk per parent path
        seen: dict[str, SearchResult] = {}
        for doc_id, document, distance in zip(ids, documents, distances):
            path = _parent_path(doc_id)
            sim  = round(max(0.0, 1.0 - distance), 4)
            if path not in seen or sim > seen[path].similarity:
                seen[path] = SearchResult(file_path=path, excerpt=(document or "")[:_CHUNK_SIZE], similarity=sim)
        out = sorted(seen.values(), key=lambda r: -r.similarity)[:top_k]
        logger.info("search: '%.50s' → %d results, top=%.2f", query, len(out), out[0].similarity if out else 0.0)
        return out

    def find_similar(
        self,
        content: str,
        exclude_path: str,
        top_k: int,
        duplicate_threshold: float = 0.85,
        related_threshold: float = 0.70,
    ) -> list[SimilarityNotice]:
        """Find notes similar to content, excluding the note itself."""
        if self._collection.count() == 0:
            return []
        embeddings = self._embedder.embed([content])
        n = min(top_k + 1, self._collection.count())
        results = self._collection.query(
            query_embeddings=embeddings,
            n_results=n,
            include=["metadatas", "distances"],
        )
        notices = []
        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]
        seen_paths: set[str] = set()
        for doc_id, distance in zip(ids, distances):
            path = _parent_path(doc_id)
            if path == exclude_path or path in seen_paths:
                continue
            seen_paths.add(path)
            similarity = max(0.0, 1.0 - distance)
            if similarity >= related_threshold:
                notices.append(SimilarityNotice(
                    matched_path=path,
                    similarity=round(similarity, 4),
                    is_duplicate=similarity >= duplicate_threshold,
                ))
            if len(notices) >= top_k:
                break
        if notices:
            logger.info(
                "find_similar: found %d similar notes for path=%s", len(notices), exclude_path
            )
        return notices

    def delete_note(self, file_path: str) -> None:
        """Remove a note (and all its chunks) from vector and BM25 indexes."""
        self._delete_from_collection(file_path)
        self._bm25.delete(file_path)
        logger.debug("delete_note: removed %s", file_path)

    def hybrid_search(self, query: str, top_k: int) -> list[SearchResult]:
        """Hybrid BM25 + vector search using Reciprocal Rank Fusion (RRF).

        Falls back to pure vector search if BM25 is not ready.
        """
        vector_results = self.search(query, top_k)
        if not self._bm25.is_ready:
            return vector_results

        bm25_raw = self._bm25.search(query, top_k)

        # Build rank lists (path → rank position)
        vector_ranked = [r.file_path for r in vector_results]
        bm25_ranked = [path for path, _, _ in bm25_raw]

        # RRF scoring
        rrf_scores: dict[str, float] = {}
        for rank, path in enumerate(vector_ranked):
            rrf_scores[path] = rrf_scores.get(path, 0.0) + 1.0 / (_RRF_K + rank + 1)
        for rank, path in enumerate(bm25_ranked):
            rrf_scores[path] = rrf_scores.get(path, 0.0) + 1.0 / (_RRF_K + rank + 1)

        # Build excerpt lookup from both result sets
        excerpts: dict[str, str] = {r.file_path: r.excerpt for r in vector_results}
        for path, _, excerpt in bm25_raw:
            if path not in excerpts:
                excerpts[path] = excerpt

        # Sort by RRF score and return top_k
        merged_paths = sorted(rrf_scores, key=lambda p: -rrf_scores[p])[:top_k]
        return [
            SearchResult(
                file_path=p,
                excerpt=excerpts.get(p, ""),
                similarity=round(rrf_scores[p], 6),
            )
            for p in merged_paths
        ]

    def count(self) -> int:
        return self._collection.count()

    def is_ready(self) -> bool:
        """True if collection exists and has at least one indexed note."""
        return self._collection.count() > 0

    def build_from_vault(self, vault_path: str, config=None) -> int:
        """Scan all .md files in vault (excluding MoC files) and upsert each. Returns count."""
        self._building = True
        try:
            vault = Path(vault_path)
            count = 0
            for md_file in vault.rglob("*.md"):
                if md_file.name.startswith("0 "):
                    continue
                try:
                    content = md_file.read_text(encoding="utf-8", errors="replace")
                    if content.strip():
                        rel_path = str(md_file.relative_to(vault))
                        self.upsert_note(rel_path, content)
                        count += 1
                except Exception as exc:
                    logger.warning("build_from_vault: failed to index %s: %s", md_file, exc)
            logger.info("build_from_vault: indexed %d notes from %s", count, vault_path)
            return count
        finally:
            self._building = False
