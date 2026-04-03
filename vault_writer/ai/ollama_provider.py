"""Ollama provider — text and vision completion via local REST API."""
from __future__ import annotations

import base64
import logging

from vault_writer.ai.provider import AIProvider

logger = logging.getLogger(__name__)

_CONNECT_TIMEOUT = 5  # seconds to establish TCP connection (fail fast if Ollama is down)
# Read timeout is None everywhere — wait indefinitely for model response


class OllamaProvider(AIProvider):
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "mistral",
        vision_model: str = "",
        timeout: int = 900,  # kept for config compat, no longer used as read timeout
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._vision_model = vision_model

    def list_models(self) -> list[str]:
        """Return list of model names available in Ollama."""
        import requests
        try:
            resp = requests.get(f"{self._base_url}/api/tags", timeout=(_CONNECT_TIMEOUT, 10))
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            return []

    def warmup(self) -> None:
        """Send a minimal request to force model load into RAM.
        Waits indefinitely until the model responds."""
        import requests
        logger.info("Ollama warmup: loading model '%s' into memory…", self._model)
        try:
            response = requests.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                    "options": {"num_predict": 1},
                },
                timeout=(_CONNECT_TIMEOUT, None),  # no read timeout
            )
            if response.status_code == 500:
                try:
                    err_body = response.json().get("error", response.text[:300])
                except Exception:
                    err_body = response.text[:300]
                available = self.list_models()
                hint = (
                    f"Available models: {', '.join(available)}"
                    if available else "No models found — run: ollama pull <model>"
                )
                logger.error("Ollama 500 detail: %s", err_body)
                raise RuntimeError(
                    f"Ollama 500 for model '{self._model}': {err_body}\n{hint}"
                )
            response.raise_for_status()
            content = response.json().get("message", {}).get("content", "")
            if not content and content != "":
                pass  # num_predict=1 may return empty on some models — that's OK
            # Verify the model actually exists by checking the response is valid JSON
            available = self.list_models()
            if available and self._model not in available:
                hint = f"Available models: {', '.join(available)}"
                raise RuntimeError(
                    f"Model '{self._model}' not found in Ollama.\n{hint}\n"
                    f"Fix: set `ai.model` in `config.yaml` to one of the listed models."
                )
            logger.info("Ollama warmup complete — model '%s' is ready", self._model)
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                f"Ollama not reachable at {self._base_url} — is it running?"
            ) from exc

    def complete(self, prompt: str, max_tokens: int = 1000) -> str:
        import requests
        logger.debug(
            "ollama.complete: model=%s max_tokens=%d prompt_len=%d",
            self._model, max_tokens, len(prompt),
        )
        try:
            response = requests.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"num_predict": max_tokens},
                },
                timeout=(_CONNECT_TIMEOUT, None),  # no read timeout
            )
            if response.status_code == 500:
                try:
                    err_body = response.json().get("error", response.text[:300])
                except Exception:
                    err_body = response.text[:300]
                logger.error("Ollama 500 detail: %s", err_body)
                raise RuntimeError(f"Ollama 500 for model '{self._model}': {err_body}")
            response.raise_for_status()
            return response.json()["message"]["content"]
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                f"Ollama not reachable at {self._base_url} — is it running? ({exc})"
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
                timeout=(_CONNECT_TIMEOUT, None),  # no read timeout
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                f"Ollama not reachable at {self._base_url} — is it running? ({exc})"
            ) from exc
