"""create_note MCP tool handler — orchestrates full note creation flow."""
from __future__ import annotations

import logging
from datetime import date as _date

from vault_writer.ai.classifier import ClassificationResult, classify
from vault_writer.ai.formatter import format_note
from vault_writer.ai.provider import ProcessingMode
from vault_writer.vault.indexer import VaultIndex, update_index
from vault_writer.vault.writer import NoteType, VaultNote, create_moc_if_missing, create_mocs_for_path, update_moc, write_note
from vault_writer.vault.writer import DATA_SUBFOLDER

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
    vector_store=None,  # VectorStore | None
    claude_code_session_tokens: int = 0,
    content_override: str | None = None,
) -> dict:
    """Orchestrate full note creation: classify → format → enrich → write → MoC → stats."""
    # Claude Code session token limit check (T067)
    if hasattr(config, 'claude_code_max_session_tokens'):
        limit = getattr(config, 'claude_code_max_session_tokens', 0)
        if limit and claude_code_session_tokens >= limit:
            return {"success": False, "error": f"Claude Code session token limit reached ({limit})"}

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

    # ── Content override (e.g. full PDF text) ─────────────────────────────────
    if content_override is not None:
        content = content_override

    # ── Enrich: semantic wikilinks (full mode) ────────────────────────────────
    # Skip when content_override is set — sending 50 pages to AI for linking is wasteful
    if content_override is None and provider is not None and mode == ProcessingMode.FULL and config.enrichment_add_wikilinks:
        try:
            from vault_writer.ai.linker import enrich_with_links
            content = enrich_with_links(content, index, vector_store, provider, config)
        except Exception as exc:
            logger.warning("enrich_with_links error: %s — skipping", exc)

    # ── Build VaultNote ───────────────────────────────────────────────────────
    note = VaultNote(
        title=classification.title,
        date=today,
        categories=[classification.folder],
        tags=[f"areas/{classification.folder.split('/')[0]}", f"types/{classification.note_type.value}"],
        moc=f"[[0 {classification.folder}]]",
        content=content,
        file_path="",           # filled by write_note
        note_type=classification.note_type,
        folder=classification.folder,
        note_number=0,          # filled by write_note
        use_data_subfolder=True,
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
            update_moc(moc_path, file_path, config.vault.path)
        except Exception as exc:
            logger.warning("update_moc error: %s", exc)

    # ── Index + Stats ─────────────────────────────────────────────────────────
    update_index(index, note)
    stats.last_note_path = file_path
    stats.notes_saved_today += 1
    stats.vault_notes_total = index.total_notes

    # ── Vector index + Similarity check ──────────────────────────────────────
    similarity_notices = []
    if vector_store is not None:
        try:
            vector_store.upsert_note(file_path, content)
            embedding_config = getattr(config, "embedding", None)
            dup_threshold = getattr(embedding_config, "similarity_duplicate_threshold", 0.85)
            rel_threshold = getattr(embedding_config, "similarity_related_threshold", 0.70)
            raw_notices = vector_store.find_similar(
                content,
                exclude_path=file_path,
                top_k=3,
                duplicate_threshold=dup_threshold,
                related_threshold=rel_threshold,
            )
            similarity_notices = [n for n in raw_notices if n.similarity >= rel_threshold]
        except Exception as exc:
            logger.warning("vector_store upsert/find_similar error: %s", exc)

    # ── Retroactive linking: update existing notes that mention this new note ─
    if config.enrichment_add_wikilinks and mode != ProcessingMode.MINIMAL:
        try:
            from vault_writer.ai.linker import retrolink_to_new_note
            retrolink_to_new_note(note.title, file_path, config.vault.path, index, config)
        except Exception as exc:
            logger.warning("retrolink error: %s", exc)

    return {
        "success": True,
        "file_path": file_path,
        "note_type": classification.note_type.value,
        "folder": classification.folder,
        "title": note.title,
        "mode_used": mode.value,
        "similarity_notices": similarity_notices,
    }


def _default_body(text: str) -> str:
    return f"## Опис\n\n{text}\n\n## Висновки\n\n## Посилання\n"


def handle_create_note_from_plan(
    text: str,
    plan,               # vault_writer.ai.router.ActionPlan
    config,
    index: VaultIndex,
    stats,
    provider=None,
    vector_store=None,
    content_override: str | None = None,
) -> dict:
    """Orchestrate note creation from a pre-built ActionPlan (from AI Router)."""
    from vault_writer.ai.router import Intent

    mode = ProcessingMode(config.ai.processing_mode)
    today = _date.today().isoformat()

    # Map router note_type string → NoteType enum
    _type_map = {
        "task": NoteType.TASK,
        "idea": NoteType.IDEA,
        "journal": NoteType.JOURNAL,
        "note": NoteType.NOTE,
    }
    note_type = _type_map.get(plan.note_type, NoteType.NOTE)

    # Build full 4-level folder path: GeneralCategory/Topic[/Subtopic][/Section]
    general_category = getattr(plan, "general_category", "") or ""
    folder = plan.target_folder or "General"
    subfolder = plan.target_subfolder or ""
    section = getattr(plan, "section", "") or ""
    path_parts = [p for p in [general_category, folder, subfolder, section] if p]
    full_folder = "/".join(path_parts) if path_parts else folder
    title = plan.title or text[:60]

    classification = ClassificationResult(
        note_type=note_type,
        topic=plan.topic or folder,
        folder=full_folder,
        parent_moc=f"0 {full_folder.split('/')[-1]}.md",
        title=title,
        confidence=plan.confidence,
    )

    # ── Format — use router-provided content first (avoids extra AI call) ─────
    if getattr(plan, "content", ""):
        content = plan.content
    elif provider is not None and mode in (ProcessingMode.BALANCED, ProcessingMode.FULL):
        try:
            content = format_note(text, classification, provider, config)
        except Exception as exc:
            logger.warning("format_note error: %s — using raw text", exc)
            content = _default_body(text)
    else:
        content = _default_body(text)

    if content_override is not None:
        content = content_override

    # ── Enrich: semantic wikilinks (full mode) ────────────────────────────────
    # Run on ALL content including router-provided (router doesn't add cross-links).
    # Skip only when content_override is set (PDFs — too large for linking).
    if content_override is None and provider is not None and mode == ProcessingMode.FULL and config.enrichment_add_wikilinks:
        try:
            from vault_writer.ai.linker import enrich_with_links
            content = enrich_with_links(content, index, vector_store, provider, config)
        except Exception as exc:
            logger.warning("enrich_with_links error: %s — skipping", exc)

    # ── Build VaultNote ───────────────────────────────────────────────────────
    tags = plan.tags or []
    # Tag with general_category if present, else top-level folder (preserve casing)
    area_tag = general_category or folder.split("/")[0]
    if not any(t.startswith("areas/") for t in tags):
        tags = [f"areas/{area_tag}", f"types/{note_type.value}"] + tags

    # MOC link points to the innermost (most specific) folder name
    innermost = full_folder.split("/")[-1] if full_folder else folder
    note = VaultNote(
        title=title,
        date=today,
        categories=[general_category or folder],
        tags=tags,
        moc=f"[[0 {innermost}]]",
        content=content,
        file_path="",
        note_type=note_type,
        folder=full_folder,
        note_number=0,
        use_data_subfolder=True,
    )

    # ── Write ─────────────────────────────────────────────────────────────────
    try:
        file_path = write_note(note, config.vault.path)
    except Exception as exc:
        logger.error("write_note failed: %s", exc)
        return {"success": False, "error": str(exc)}

    # ── MoC (create at each folder level and link hierarchy) ─────────────────
    if config.enrichment_update_moc:
        try:
            moc_path = create_mocs_for_path(full_folder, config.vault.path)
            update_moc(moc_path, file_path, config.vault.path)
        except Exception as exc:
            logger.warning("update_moc error: %s", exc)

    # ── Register folder in vault structure index ──────────────────────────────
    try:
        from vault_writer.vault.structure import register_folder
        register_folder(config.vault.path, full_folder)
    except Exception as exc:
        logger.debug("register_folder: %s", exc)

    # ── Index + Stats ─────────────────────────────────────────────────────────
    update_index(index, note)
    stats.last_note_path = file_path
    stats.notes_saved_today += 1
    stats.vault_notes_total = index.total_notes

    # ── Vector store ──────────────────────────────────────────────────────────
    similarity_notices = []
    if vector_store is not None:
        try:
            vector_store.upsert_note(file_path, content)
            emb_cfg = getattr(config, "embedding", None)
            dup_thr = getattr(emb_cfg, "similarity_duplicate_threshold", 0.85)
            rel_thr = getattr(emb_cfg, "similarity_related_threshold", 0.70)
            raw_notices = vector_store.find_similar(
                content, exclude_path=file_path, top_k=3,
                duplicate_threshold=dup_thr, related_threshold=rel_thr,
            )
            similarity_notices = [n for n in raw_notices if n.similarity >= rel_thr]
        except Exception as exc:
            logger.warning("vector_store error: %s", exc)

    # ── Retroactive linking: update existing notes that mention this new note ─
    if config.enrichment_add_wikilinks and mode != ProcessingMode.MINIMAL:
        try:
            from vault_writer.ai.linker import retrolink_to_new_note
            retrolink_to_new_note(title, file_path, config.vault.path, index, config)
        except Exception as exc:
            logger.warning("retrolink error: %s", exc)

    return {
        "success": True,
        "file_path": file_path,
        "note_type": note_type.value,
        "folder": full_folder,
        "title": title,
        "similarity_notices": similarity_notices,
    }
