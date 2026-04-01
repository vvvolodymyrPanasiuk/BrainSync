"""Telegram message formatters — all system strings go through i18n.t()."""
from __future__ import annotations

from telegram.i18n import t


def format_confirmation(file_path: str) -> str:
    return t("saved", file_path=file_path)


def format_search_results(results: list[dict], query: str) -> str:
    if not results:
        return t("search_not_found", query=query)
    lines = [t("search_found", count=len(results), query=query)]
    for i, r in enumerate(results, 1):
        excerpt = r.get("excerpt", "")
        lines.append(f"{i}. {r['file_path']}\n   ...{excerpt}...")
    return "\n".join(lines)


def format_status(config, stats, index) -> str:
    return (
        "📊 BrainSync Status\n\n"
        f"Mode: {config.ai.processing_mode}\n"
        f"Provider: {config.ai.provider} ({config.ai.model})\n"
        f"Tokens: {stats.tokens_consumed:,}\n"
        f"Last note: {stats.last_note_path or '—'}\n"
        f"Notes today: {stats.notes_saved_today}\n"
        f"Total notes: {stats.vault_notes_total}\n"
        f"Vault context: {index.total_notes} notes"
    )


def format_mode_confirmation(mode: str) -> str:
    return t("mode_changed", mode=mode)


def format_ai_fallback(file_path: str) -> str:
    return t("ai_fallback", file_path=file_path)


def format_voice_duration_error(max_seconds: int) -> str:
    return t("voice_too_long", max_seconds=max_seconds)


def format_media_processing_error() -> str:
    return t("media_error")


def format_unsupported_file_type() -> str:
    return t("unsupported_file")


def format_model_downloading() -> str:
    return t("model_downloading")


def format_model_ready() -> str:
    return t("model_ready")


def format_pdf_scanned_error() -> str:
    return t("pdf_scanned")


def format_pdf_truncated_notice(pages: int) -> str:
    return t("pdf_truncated", pages=pages)


def format_file_too_large(max_mb: int) -> str:
    return t("file_too_large", max_mb=max_mb)


def format_unsupported_media_types() -> str:
    return t("unsupported_media")


def format_bot_online() -> str:
    return t("bot_online")


def format_bot_offline() -> str:
    return t("bot_offline")


# ── RAG / Semantic Search formatters ─────────────────────────────────────────

def format_chat_reply(answer: str) -> str:
    return answer


def format_rag_answer(answer: str, sources: list[str]) -> str:
    lines = [t("rag_prefix"), answer]
    if sources:
        lines.append(t("rag_sources"))
        for src in sources:
            lines.append(f"→ {src}")
    return "\n".join(lines)


def format_rag_not_found() -> str:
    return t("rag_not_found")


def format_semantic_search_results(results: list, query: str) -> str:
    if not results:
        return t("search_not_found", query=query)
    lines = [t("search_found", count=len(results), query=query)]
    for i, r in enumerate(results, 1):
        pct = int(r.similarity * 100)
        lines.append(f"{i}. {r.file_path} ({pct}%)\n   ...{r.excerpt[:200]}...")
    return "\n".join(lines)


def format_search_degraded_notice() -> str:
    return t("search_degraded")


def format_similarity_notice(notices: list) -> str:
    if not notices:
        return ""
    lines = []
    for notice in notices:
        pct = int(notice.similarity * 100)
        key = "duplicate_note" if notice.is_duplicate else "related_note"
        lines.append(t(key, path=notice.matched_path, pct=pct))
    return "\n".join(lines)


def format_reindex_start() -> str:
    return t("reindex_start")


def format_reindex_done(count: int) -> str:
    return t("reindex_done", count=count)


def format_index_building_notice() -> str:
    return t("index_building")
