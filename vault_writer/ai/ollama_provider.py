"""Ollama provider stub — placeholder for v1.1."""
from __future__ import annotations

from vault_writer.ai.provider import AIProvider


class OllamaProvider(AIProvider):
    def complete(self, prompt: str, max_tokens: int = 1000) -> str:
        raise NotImplementedError("OllamaProvider is not implemented in v1. Planned for v1.1.")
