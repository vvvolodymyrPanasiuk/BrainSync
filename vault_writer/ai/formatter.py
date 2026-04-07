"""AI formatter: format raw text into structured note markdown body."""
from __future__ import annotations

import logging

from vault_writer.ai.classifier import ClassificationResult
from vault_writer.ai.provider import AIProvider

logger = logging.getLogger(__name__)


def format_note(
    text: str,
    classification: ClassificationResult,
    provider: AIProvider,
    config,     # AppConfig
) -> str:
    """Format raw text into structured markdown body. Returns formatted content string."""
    agents_content = _read_file_safe(config.ai.agents_file)
    vault_writer_skill = _read_file_safe(config.ai.skills_path + "vault-writer.md")
    obsidian_rules = _read_file_safe(config.ai.skills_path + "obsidian-rules.md")

    prompt = (
        f"{agents_content}\n\n"
        f"{vault_writer_skill}\n\n"
        f"{obsidian_rules}\n\n"
        f"Type: {classification.note_type.value}\n"
        f"Topic: {classification.topic}\n"
        f"Folder: {classification.folder}\n"
        f"Vault locale: {config.vault.language}\n\n"
        f"Format the following text as a structured Obsidian note body with three sections: "
        f"Description, Conclusions, Links — translated to the vault locale above. "
        f"Return only the markdown body, no frontmatter:\n\n{text}"
    )

    try:
        return provider.complete(prompt, max_tokens=800)
    except Exception as exc:
        logger.warning("format_note failed: %s — returning raw text", exc)
        return f"## Опис\n\n{text}\n\n## Висновки\n\n## Посилання\n"


def _read_file_safe(path: str) -> str:
    try:
        from pathlib import Path
        return Path(path).read_text(encoding="utf-8")
    except Exception:
        return ""
