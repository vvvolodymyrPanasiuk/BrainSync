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

    def warmup(self) -> None:
        """Pre-load the model so first real request is fast. No-op by default."""

    def complete_with_image(
        self,
        prompt: str,
        image_bytes: bytes,
        media_type: str,
        max_tokens: int = 1000,
    ) -> str:
        """Send prompt + image, return completion text. Override in vision-capable providers."""
        raise NotImplementedError("Vision not supported by this provider")
