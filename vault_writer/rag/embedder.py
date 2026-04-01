"""Embedding providers: abstract base + SentenceTransformers + Ollama implementations."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts. Returns list of float vectors."""
        ...


class SentenceTransformersEmbedder(EmbeddingProvider):
    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model = None  # lazy load

    def _load(self) -> None:
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading sentence-transformers model: %s", self._model_name)
            self._model = SentenceTransformer(self._model_name)
            logger.info("sentence-transformers model loaded")

    def embed(self, texts: list[str]) -> list[list[float]]:
        self._load()
        return self._model.encode(texts).tolist()


class OllamaEmbedder(EmbeddingProvider):
    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        import requests
        results = []
        for text in texts:
            resp = requests.post(
                f"{self._base_url}/api/embeddings",
                json={"model": self._model, "prompt": text},
                timeout=30,
            )
            if not resp.ok:
                raise RuntimeError(
                    f"Ollama embeddings error {resp.status_code}: {resp.text[:200]}"
                )
            results.append(resp.json()["embedding"])
        return results
