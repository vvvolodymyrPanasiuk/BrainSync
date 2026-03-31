"""RAG engine: answer_query, search_vault, and result dataclasses."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RAGResult:
    answer: str
    sources: list[str]
    query: str
    found: bool


@dataclass
class SearchResult:
    file_path: str
    excerpt: str
    similarity: float


@dataclass
class SimilarityNotice:
    matched_path: str
    similarity: float
    is_duplicate: bool


_RAG_PROMPT = """\
You are a personal knowledge assistant. Answer the user's question ONLY based on the provided notes \
from their personal vault. Do NOT use general knowledge — only synthesize information found in the notes below.
If the notes do not contain relevant information, say you didn't find anything relevant.
Answer in the same language as the question.

Notes from vault:
{context}

Question: {query}

Answer:"""


def answer_query(query: str, store, provider, top_k: int, config=None) -> RAGResult:
    """Retrieve relevant notes and generate a RAG answer grounded in vault content."""
    results = store.search(query, top_k)
    if not results:
        logger.info("RAG query returned no results for: %.50s", query)
        return RAGResult(answer="", sources=[], query=query, found=False)

    context_parts = []
    sources = []
    for r in results:
        context_parts.append(f"[{r.file_path}]\n{r.excerpt}")
        sources.append(r.file_path)

    context = "\n\n---\n\n".join(context_parts)
    prompt = _RAG_PROMPT.format(context=context, query=query)

    answer = provider.complete(prompt)
    logger.info("RAG answer generated from %d sources for query: %.50s", len(sources), query)
    return RAGResult(answer=answer, sources=sources, query=query, found=True)


def search_vault(query: str, store, top_k: int) -> list[SearchResult]:
    """Semantic vault search — delegates to VectorStore.search()."""
    return store.search(query, top_k)
