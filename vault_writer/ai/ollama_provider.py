"""Ollama provider — text and vision completion via local REST API."""
from __future__ import annotations

import base64
import logging

from vault_writer.ai.provider import AIProvider

logger = logging.getLogger(__name__)

_CONNECT_TIMEOUT = 5  # seconds to establish TCP connection (fail fast if Ollama is down)
# Read timeout is None everywhere — wait indefinitely for model response


def _extract_content(body: dict) -> str:
    """Universally extract assistant text from any Ollama response shape.

    Ollama local models:   body["message"]["content"]
    Ollama cloud proxies:  body["message"]["content"]  (same, but may be "")
    Some providers also:   body["response"]  (generate endpoint compatibility)
    Last resort:           stringify the whole body so we never return silently.
    """
    # Primary: standard chat response
    msg = body.get("message") or {}
    content = msg.get("content")
    if content:
        return content

    # Secondary: generate-style response field
    content = body.get("response")
    if content:
        return content

    # If both are empty strings (model produced no tokens), log full body for debugging
    logger.warning("_extract_content: both message.content and response are empty. full body: %s", body)
    return ""


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
                    "options": {},
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
                    # num_predict: -1 = unlimited — required for thinking models
                    # (e.g. kimi, qwen3, deepseek-r1) that spend tokens on <think> blocks
                    # before producing the actual response content.
                    "options": {},
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
            try:
                body = response.json()
            except Exception:
                raise RuntimeError(
                    f"Ollama returned non-JSON response (status {response.status_code}): "
                    f"{response.text[:300]}"
                )
            return _extract_content(body)
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
                    "options": {},
                },
                timeout=(_CONNECT_TIMEOUT, None),  # no read timeout
            )
            response.raise_for_status()
            try:
                body = response.json()
            except Exception:
                raise RuntimeError(
                    f"Ollama returned non-JSON response: {response.text[:300]}"
                )
            return _extract_content(body)
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                f"Ollama not reachable at {self._base_url} — is it running? ({exc})"
            ) from exc
