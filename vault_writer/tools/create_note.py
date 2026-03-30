"""create_note MCP tool handler — orchestrates full note creation flow."""
from __future__ import annotations

import logging
from datetime import date as _date

from vault_writer.ai.classifier import ClassificationResult, classify
from vault_writer.ai.formatter import format_note
from vault_writer.ai.provider import ProcessingMode
from vault_writer.vault.indexer import VaultIndex, update_index
from vault_writer.vault.writer import NoteType, VaultNote, create_moc_if_missing, update_moc, write_note

logger = logging.getLogger(__name__)


def detect_prefix(text: str, prefixes: dict) -> tuple[NoteType | None, str]:
    """Case-insensitive prefix match at start of message. Returns (NoteType|None, stripped_text)."""
    lower = text.lower().lstrip()
    type_map = {
        "note": NoteType.NOTE,
        "task": NoteType.TASK,
        "idea": NoteType.IDEA,
        "journal": NoteType.JOURNAL,
    }
    for type_key, prefix_list in prefixes.items():
        for prefix in prefix_list:
            if lower.startswith(prefix.lower()):
                stripped = text[text.lower().find(prefix.lower()) + len(prefix):].strip()
                return type_map.get(type_key), stripped
    return None, text


def handle_create_note(
    text: str,
    type_: NoteType | None,
    folder: str | None,
    config,         # AppConfig
    index: VaultIndex,
    stats,          # SessionStats
    provider=None,  # AIProvider | None
) -> dict:
    """Orchestrate full note creation: classify → format → enrich → write → MoC → stats."""
    mode = ProcessingMode(config.ai.processing_mode)
    today = _date.today().isoformat()

    # ── Classify ──────────────────────────────────────────────────────────────
    classification: ClassificationResult | None = None

    if type_ is not None and folder is not None:
        # Explicit type + folder from command — skip AI classify
        classification = ClassificationResult(
            note_type=type_,
            topic=folder,
            folder=folder,
            parent_moc=f"0 {folder}.md",
            title=text[:60],
            confidence=1.0,
        )
    elif provider is not None and mode != ProcessingMode.MINIMAL:
        try:
            classification = classify(text, provider, index, config)
        except Exception as exc:
            logger.warning("classify error: %s — falling back to minimal", exc)

    if classification is None:
        # Minimal fallback
        note_type = type_ or NoteType.NOTE
        folder_name = folder or "General"
        classification = ClassificationResult(
            note_type=note_type,
            topic=folder_name,
            folder=folder_name,
            parent_moc=f"0 {folder_name}.md",
            title=text[:60],
            confidence=0.0,
        )

    # ── Format ────────────────────────────────────────────────────────────────
    if provider is not None and mode in (ProcessingMode.BALANCED, ProcessingMode.FULL):
        try:
            content = format_note(text, classification, provider, config)
        except Exception as exc:
            logger.warning("format_note error: %s — using raw text", exc)
            content = _default_body(text)
    else:
        content = _default_body(text)

    # ── Enrich (full mode) ────────────────────────────────────────────────────
    if provider is not None and mode == ProcessingMode.FULL and config.enrichment_add_wikilinks:
        try:
            from vault_writer.ai.enricher import add_wikilinks
            content = add_wikilinks(content, index, config)
        except Exception as exc:
            logger.warning("add_wikilinks error: %s — skipping enrichment", exc)

    # ── Build VaultNote ───────────────────────────────────────────────────────
    note = VaultNote(
        title=classification.title,
        date=today,
        categories=[classification.folder],
        tags=[f"areas/{classification.folder.lower()}", f"types/{classification.note_type.value}"],
        moc=f"[[0 {classification.folder}]]",
        content=content,
        file_path="",           # filled by write_note
        note_type=classification.note_type,
        folder=classification.folder,
        note_number=0,          # filled by write_note
    )

    # ── Write ─────────────────────────────────────────────────────────────────
    try:
        file_path = write_note(note, config.vault.path)
    except Exception as exc:
        logger.error("write_note failed: %s", exc)
        return {"success": False, "error": str(exc)}

    # ── MoC ───────────────────────────────────────────────────────────────────
    if config.enrichment_update_moc:
        try:
            moc_path = create_moc_if_missing(classification.folder, config.vault.path)
            update_moc(moc_path, file_path, note.title, note.note_number, config.vault.path)
        except Exception as exc:
            logger.warning("update_moc error: %s", exc)

    # ── Index + Stats ─────────────────────────────────────────────────────────
    update_index(index, note)
    stats.last_note_path = file_path
    stats.notes_saved_today += 1
    stats.vault_notes_total = index.total_notes

    return {
        "success": True,
        "file_path": file_path,
        "note_type": classification.note_type.value,
        "folder": classification.folder,
        "title": note.title,
        "mode_used": mode.value,
    }


def _default_body(text: str) -> str:
    return f"## Description\n\n{text}\n\n## Conclusions\n\n## Links\n"
