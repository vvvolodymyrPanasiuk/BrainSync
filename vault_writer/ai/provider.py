"""AIProvider abstract base class."""
from __future__ import annotations

from abc import ABC, abstractmethod


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
