"""Telegram message formatters."""
from __future__ import annotations


def format_confirmation(file_path: str) -> str:
    return f"✓ Збережено → {file_path}"


def format_search_results(results: list[dict], query: str) -> str:
    if not results:
        return f'Нічого не знайдено для "{query}"'
    lines = [f'🔍 Знайдено {len(results)} нотаток для "{query}":\n']
    for i, r in enumerate(results, 1):
        excerpt = r.get("excerpt", "")
        lines.append(f"{i}. {r['file_path']}\n   ...{excerpt}...")
    return "\n".join(lines)


def format_status(config, stats, index) -> str:
    return (
        "📊 BrainSync Status\n\n"
        f"Режим: {config.ai.processing_mode}\n"
        f"Провайдер: {config.ai.provider} ({config.ai.model})\n"
        f"Токени сесії: {stats.tokens_consumed:,}\n"
        f"Остання нотатка: {stats.last_note_path or '—'}\n"
        f"Нотаток сьогодні: {stats.notes_saved_today}\n"
        f"Всього нотаток: {stats.vault_notes_total}\n"
        f"Контекст vault: {index.total_notes} нотаток"
    )


def format_mode_confirmation(mode: str) -> str:
    return (
        f"✓ Режим змінено на: {mode}\n"
        "⚠️ Набере чинності після перезапуску бота."
    )


def format_ai_fallback(file_path: str) -> str:
    return (
        "⚠️ AI недоступний (rate limit). Нотатку збережено у minimal режимі.\n"
        f"→ {file_path}"
    )


def format_voice_duration_error(max_seconds: int) -> str:
    return f"⚠️ Голосове повідомлення надто довге. Максимум: {max_seconds} секунд."


def format_media_processing_error() -> str:
    return "❌ Помилка обробки медіа. Спробуйте ще раз."


def format_unsupported_file_type() -> str:
    return "⚠️ Непідтримуваний тип файлу. Підтримуються: pdf, txt, md."


def format_model_downloading() -> str:
    return "⏳ Завантаження моделі транскрипції…"


def format_model_ready() -> str:
    return "✅ Модель готова. BrainSync запущено."


def format_pdf_scanned_error() -> str:
    return "⚠️ PDF містить лише відскановані зображення — текст недоступний."


def format_pdf_truncated_notice(pages: int) -> str:
    return f"ℹ️ PDF обрізано: збережено перших {pages} сторінок."


def format_file_too_large(max_mb: int) -> str:
    return f"⚠️ Файл надто великий. Максимум: {max_mb} МБ."


def format_unsupported_media_types() -> str:
    return "⚠️ Непідтримуваний тип медіа. Підтримуються: голосові, фото, PDF, txt, md."


# ── RAG / Semantic Search formatters ─────────────────────────────────────────

def format_chat_reply(answer: str) -> str:
    return answer


def format_rag_answer(answer: str, sources: list[str]) -> str:
    lines = ["💡 На основі твого vault:\n", answer]
    if sources:
        lines.append("\nДжерела:")
        for src in sources:
            lines.append(f"→ {src}")
    return "\n".join(lines)


def format_rag_not_found() -> str:
    return "🔍 Нічого не знайдено у vault за цим запитом."


def format_semantic_search_results(results: list, query: str) -> str:
    if not results:
        return f'Нічого не знайдено для "{query}"'
    lines = [f'🔍 Знайдено {len(results)} нотаток для "{query}":\n']
    for i, r in enumerate(results, 1):
        pct = int(r.similarity * 100)
        lines.append(f"{i}. {r.file_path} ({pct}%)\n   ...{r.excerpt[:200]}...")
    return "\n".join(lines)


def format_search_degraded_notice() -> str:
    return "⚠️ Семантичний пошук недоступний — використовую keyword пошук."


def format_similarity_notice(notices: list) -> str:
    if not notices:
        return ""
    lines = []
    for notice in notices:
        pct = int(notice.similarity * 100)
        if notice.is_duplicate:
            lines.append(f"⚠️ Схожа нотатка вже існує:\n→ {notice.matched_path} ({pct}%)")
        else:
            lines.append(f"💡 Можливо пов'язана нотатка:\n→ {notice.matched_path} ({pct}%)")
    return "\n".join(lines)


def format_reindex_start() -> str:
    return "⏳ Переіндексація vault…"


def format_reindex_done(count: int) -> str:
    return f"✅ Переіндексовано: {count} нотаток."


def format_index_building_notice() -> str:
    return "⏳ Індекс будується — результати можуть бути неповними."
