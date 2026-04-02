"""Ollama provider — text and vision completion via local REST API."""
from __future__ import annotations

import base64
import logging

from vault_writer.ai.provider import AIProvider

logger = logging.getLogger(__name__)

# Separate timeouts: connect fast, allow longer generation
_CONNECT_TIMEOUT = 5   # seconds to establish TCP connection
_WARMUP_TIMEOUT  = 900 # seconds for cold-start warmup ping (model load)


class OllamaProvider(AIProvider):
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "mistral",
        vision_model: str = "",
        timeout: int = 900,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._vision_model = vision_model
        self._timeout = timeout  # configurable via config.yaml ai.ollama_timeout

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
        """Send a minimal request to force model load into VRAM/RAM.
        Blocks until the model is ready. Uses _WARMUP_TIMEOUT (15 min).
        Raises RuntimeError if Ollama is unreachable, model missing, or times out."""
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
                timeout=(_CONNECT_TIMEOUT, _WARMUP_TIMEOUT),
            )
            if response.status_code == 500:
                available = self.list_models()
                hint = (
                    f"Available models: {', '.join(available)}"
                    if available else "No models found — run: ollama pull <model>"
                )
                raise RuntimeError(
                    f"Ollama returned 500 for model '{self._model}' — model not found or failed to load.\n"
                    f"{hint}\n"
                    f"Fix: set ai.model in config.yaml to one of the available models."
                )
            response.raise_for_status()
            logger.info("Ollama warmup complete — model '%s' is ready", self._model)
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                f"Ollama not reachable at {self._base_url} — is it running?"
            ) from exc
        except requests.exceptions.ReadTimeout as exc:
            raise RuntimeError(
                f"Ollama warmup timed out after {_WARMUP_TIMEOUT}s — model did not load"
            ) from exc

    def complete(self, prompt: str, max_tokens: int = 1000) -> str:
        import requests
        timeout = (_CONNECT_TIMEOUT, self._timeout)
        logger.debug(
            "ollama.complete: model=%s max_tokens=%d timeout=%ds prompt_len=%d",
            self._model, max_tokens, self._timeout, len(prompt),
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
                timeout=timeout,
            )
            if response.status_code == 500:
                available = self.list_models()
                hint = (
                    f"Available models: {', '.join(available)}"
                    if available else "No models found — run: ollama pull <model>"
                )
                raise RuntimeError(
                    f"Ollama 500 for model '{self._model}' — model not found.\n"
                    f"{hint}"
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
