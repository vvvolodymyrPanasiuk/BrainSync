"""classify_content MCP tool handler."""
from __future__ import annotations

from vault_writer.ai.classifier import classify


def handle_classify_content(text: str, provider, index, config) -> dict:
    """Classify text and return result dict per contracts/mcp-tools.md."""
    result = classify(text, provider, index, config)
    return {
        "note_type": result.note_type.value,
        "topic": result.topic,
        "folder": result.folder,
        "parent_moc": result.parent_moc,
        "title": result.title,
        "confidence": result.confidence,
    }
