"""AI classifier: classify raw text into NoteType + folder + title."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from vault_writer.ai.provider import AIProvider
from vault_writer.vault.writer import NoteType

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    note_type: NoteType
    topic: str
    folder: str
    parent_moc: str
    title: str
    confidence: float   # 0.0–1.0; below 0.5 triggers minimal mode fallback


def classify(
    text: str,
    provider: AIProvider,
    vault_index,        # VaultIndex — avoid circular import with TYPE_CHECKING
    config,             # AppConfig
) -> ClassificationResult:
    """Classify raw text using AI. Returns ClassificationResult."""
    agents_content = _read_file_safe(config.ai.agents_file)
    classifier_skill = _read_file_safe(config.ai.skills_path + "classifier.md")
    topics_hint = ", ".join(vault_index.topics[:30]) if vault_index.topics else "none yet"

    prompt = (
        f"{agents_content}\n\n"
        f"{classifier_skill}\n\n"
        f"Known topics in vault: {topics_hint}\n\n"
        f"Classify this text and respond ONLY with valid JSON:\n\n{text}\n\n"
        'Respond with: {"type": "note|task|idea|journal", "topic": "...", '
        '"folder": "...", "parent_moc": "0 Topic.md", "title": "...", "confidence": 0.0}'
    )

    try:
        raw = provider.complete(prompt, max_tokens=300)
        # Strip to JSON — find first { to handle any preamble
        json_start = raw.find("{")
        json_end = raw.rfind("}") + 1
        data = json.loads(raw[json_start:json_end])
        result = ClassificationResult(
            note_type=NoteType(data.get("type", "note")),
            topic=data.get("topic", "General"),
            folder=data.get("folder", "General"),
            parent_moc=data.get("parent_moc", "0 General.md"),
            title=data.get("title", text[:50]),
            confidence=float(data.get("confidence", 0.8)),
        )
        if config.logging_log_ai_decisions:
            logger.info(
                "classify: type=%s folder=%s confidence=%.2f",
                result.note_type, result.folder, result.confidence,
            )
        return result
    except Exception as exc:
        logger.warning("classify failed: %s — using minimal fallback", exc)
        return ClassificationResult(
            note_type=NoteType.NOTE,
            topic="General",
            folder="General",
            parent_moc="0 General.md",
            title=text[:60],
            confidence=0.0,
        )


def _read_file_safe(path: str) -> str:
    try:
        from pathlib import Path
        return Path(path).read_text(encoding="utf-8")
    except Exception:
        return ""
