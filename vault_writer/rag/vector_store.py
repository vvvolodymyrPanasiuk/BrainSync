"""VectorStore: ChromaDB wrapper for vault note embeddings + BM25 hybrid search."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from vault_writer.rag.embedder import EmbeddingProvider
from vault_writer.rag.engine import SearchResult, SimilarityNotice

logger = logging.getLogger(__name__)

_COLLECTION_NAME = "vault_notes"
_RRF_K = 60  # standard RRF constant


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
        """Embed and upsert a note; skip vector update if content hash unchanged."""
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        existing = self._collection.get(ids=[file_path], include=["metadatas"])
        if existing["ids"] and existing["metadatas"][0].get("hash") == content_hash:
            logger.debug("upsert_note: unchanged hash, skipping vector update for %s", file_path)
        else:
            embeddings = self._embedder.embed([content])
            self._collection.upsert(
                ids=[file_path],
                embeddings=embeddings,
                documents=[content],
                metadatas=[{"hash": content_hash, "path": file_path}],
            )
            logger.debug("upsert_note: indexed %s (hash=%s)", file_path, content_hash[:8])
        # Always keep BM25 in sync (fast, no embeddings)
        self._bm25.upsert(file_path, content)

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        """Semantic search over vault notes. Returns ranked SearchResult list."""
        if self._collection.count() == 0:
            return []
        embeddings = self._embedder.embed([query])
        results = self._collection.query(
            query_embeddings=embeddings,
            n_results=min(top_k, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        search_results = []
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]
        for doc_id, document, distance in zip(ids, documents, distances):
            similarity = max(0.0, 1.0 - distance)
            excerpt = document[:300] if document else ""
            search_results.append(SearchResult(
                file_path=doc_id,
                excerpt=excerpt,
                similarity=round(similarity, 4),
            ))
        logger.info(
            "search: query='%.50s' returned %d results, top_similarity=%.2f",
            query,
            len(search_results),
            search_results[0].similarity if search_results else 0.0,
        )
        return search_results

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
        for doc_id, distance in zip(ids, distances):
            if doc_id == exclude_path:
                continue
            similarity = max(0.0, 1.0 - distance)
            if similarity >= related_threshold:
                notices.append(SimilarityNotice(
                    matched_path=doc_id,
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
        """Remove a note from the vector and BM25 indexes."""
        self._collection.delete(ids=[file_path])
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
