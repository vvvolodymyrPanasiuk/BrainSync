"""AIProvider abstract base class and ProcessingMode enum."""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum


class ProcessingMode(str, Enum):
    MINIMAL  = "minimal"    # 0–1 AI calls: classify only (or skip if prefix given)
    BALANCED = "balanced"   # 1–2 AI calls: classify + format
    FULL     = "full"       # 2–3 AI calls: classify + format + enrich (wikilinks)


class AIProvider(ABC):
    """Abstract interface for AI completion providers."""

    @abstractmethod
    def complete(self, prompt: str, max_tokens: int = 1000) -> str:
        """Send prompt, return completion text."""
        ...
