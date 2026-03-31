"""Anthropic Claude provider implementation."""
from __future__ import annotations

import base64

import anthropic

from vault_writer.ai.provider import AIProvider


class AnthropicProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete(self, prompt: str, max_tokens: int = 1000) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    def complete_with_image(
        self,
        prompt: str,
        image_bytes: bytes,
        media_type: str,
        max_tokens: int = 1000,
    ) -> str:
        b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
            return response.content[0].text
        except anthropic.BadRequestError as exc:
            raise NotImplementedError("Vision not supported by configured model") from exc
