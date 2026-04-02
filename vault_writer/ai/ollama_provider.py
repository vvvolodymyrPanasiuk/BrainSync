"""Ollama provider — text and vision completion via local REST API."""
from __future__ import annotations

import base64
import logging

from vault_writer.ai.provider import AIProvider

logger = logging.getLogger(__name__)

# Separate timeouts: connect fast, allow longer generation
_CONNECT_TIMEOUT = 5  # seconds to establish TCP connection


class OllamaProvider(AIProvider):
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "mistral",
        vision_model: str = "",
        timeout: int = 120,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._vision_model = vision_model
        self._timeout = timeout  # configurable via config.yaml ai.ollama_timeout

    def complete(self, prompt: str, max_tokens: int = 1000) -> str:
        import requests
        timeout = (_CONNECT_TIMEOUT, self._timeout)
        try:
            response = requests.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"num_predict": max_tokens},
                },
                timeout=timeout,
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                f"Ollama not reachable at {self._base_url} — is it running? ({exc})"
            ) from exc
        except requests.exceptions.ReadTimeout as exc:
            raise RuntimeError(
                f"Ollama timed out after {timeout[1]}s — model may be loading or too slow"
            ) from exc

    def complete_with_image(
        self,
        prompt: str,
        image_bytes: bytes,
        media_type: str,
        max_tokens: int = 1000,
    ) -> str:
        if not self._vision_model:
            raise NotImplementedError("ollama_vision_model not configured")
        import requests
        b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
        try:
            response = requests.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._vision_model,
                    "messages": [{
                        "role": "user",
                        "content": prompt,
                        "images": [b64],
                    }],
                    "stream": False,
                    "options": {"num_predict": max_tokens},
                },
                timeout=(_CONNECT_TIMEOUT, self._timeout),
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                f"Ollama not reachable at {self._base_url} — is it running? ({exc})"
            ) from exc
        except requests.exceptions.ReadTimeout as exc:
            raise RuntimeError(
                f"Ollama vision timed out — model may be loading or too slow"
            ) from exc
