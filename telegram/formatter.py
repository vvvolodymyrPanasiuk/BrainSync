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
