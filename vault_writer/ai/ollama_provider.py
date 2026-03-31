"""Ollama provider — text and vision completion via local REST API."""
from __future__ import annotations

import base64

import requests

from vault_writer.ai.provider import AIProvider


class OllamaProvider(AIProvider):
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "mistral",
        vision_model: str = "",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._vision_model = vision_model

    def complete(self, prompt: str, max_tokens: int = 1000) -> str:
        response = requests.post(
            f"{self._base_url}/api/chat",
            json={
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    def complete_with_image(
        self,
        prompt: str,
        image_bytes: bytes,
        media_type: str,
        max_tokens: int = 1000,
    ) -> str:
        if not self._vision_model:
            raise NotImplementedError("ollama_vision_model not configured")
        b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
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
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]
