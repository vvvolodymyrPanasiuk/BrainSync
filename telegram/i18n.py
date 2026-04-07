"""Simple locale support for BrainSync system messages."""
from __future__ import annotations

_locale: str = "en"

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "bot_online":         "🟢 BrainSync online — ready.",
        "bot_offline":        "🔴 BrainSync offline — bot stopped.",
        "saved":              "✓ Saved → `{file_path}`",
        "ai_fallback":        "⚠️ AI unavailable (rate limit). Note saved in minimal mode.\n→ {file_path}",
        "voice_too_long":     "⚠️ Voice message too long. Maximum: {max_seconds} seconds.",
        "media_error":        "❌ Media processing error. Please try again.",
        "unsupported_file":   "⚠️ Unsupported file type. Supported: pdf, txt, md.",
        "model_downloading":  "⏳ Downloading transcription model…",
        "model_ready":        "✅ Model ready. BrainSync started.",
        "pdf_scanned":        "⚠️ PDF contains only scanned images — text unavailable.",
        "pdf_truncated":      "ℹ️ PDF truncated: saved first {pages} pages.",
        "file_too_large":     "⚠️ File too large. Maximum: {max_mb} MB.",
        "unsupported_media":  "⚠️ Unsupported media type. Supported: voice, photo, PDF, txt, md.",
        "rag_prefix":         "💡 From your vault:\n",
        "rag_sources":        "\nSources:",
        "rag_not_found":      "🔍 Nothing found in vault for this query.",
        "search_not_found":   'Nothing found for "{query}"',
        "search_found":       '🔍 Found {count} notes for "{query}":\n',
        "index_building":     "⏳ Index is being built — results may be incomplete.",
        "search_degraded":    "⚠️ Semantic search unavailable — using keyword search.",
        "reindex_start":      "⏳ Re-indexing vault…",
        "reindex_done":       "✅ Re-indexed: {count} notes.",
        "mode_changed":       "✓ Mode changed to: {mode}\n⚠️ Takes effect after restart.",
        "error_prefix":       "❌ Error: {error}",
        "ai_unavailable":     "❌ AI provider is not responding. Check that Ollama is running and the model is loaded, or verify your API key.",
        "ai_not_ready":       "⚠️ BrainSync is not ready yet — AI failed to load on startup. Check the error message sent at startup and restart the bot.",
        "duplicate_note":     "⚠️ Similar note already exists:\n→ {path} ({pct}%)\n💡 Merge with it? /merge",
        "related_note":       "💡 Possibly related note:\n→ {path} ({pct}%)",
        "merge_no_pending":   "No pending merge. Save a note first — if a duplicate is detected, /merge will be shown.",
        "merge_done":         "✅ Merged into `{dest}`\nDeleted: `{src}`",
        "merge_failed":       "❌ Merge failed: {error}",
        "merge_files_gone":   "❌ Cannot merge: one of the files no longer exists.",
    },
    "uk": {
        "bot_online":         "🟢 BrainSync online — готовий до роботи.",
        "bot_offline":        "🔴 BrainSync offline — бот зупинено.",
        "saved":              "✓ Збережено → `{file_path}`",
        "ai_fallback":        "⚠️ AI недоступний (rate limit). Нотатку збережено у minimal режимі.\n→ {file_path}",
        "voice_too_long":     "⚠️ Голосове повідомлення надто довге. Максимум: {max_seconds} секунд.",
        "media_error":        "❌ Помилка обробки медіа. Спробуйте ще раз.",
        "unsupported_file":   "⚠️ Непідтримуваний тип файлу. Підтримуються: pdf, txt, md.",
        "model_downloading":  "⏳ Завантаження моделі транскрипції…",
        "model_ready":        "✅ Модель готова. BrainSync запущено.",
        "pdf_scanned":        "⚠️ PDF містить лише відскановані зображення — текст недоступний.",
        "pdf_truncated":      "ℹ️ PDF обрізано: збережено перших {pages} сторінок.",
        "file_too_large":     "⚠️ Файл надто великий. Максимум: {max_mb} МБ.",
        "unsupported_media":  "⚠️ Непідтримуваний тип медіа. Підтримуються: голосові, фото, PDF, txt, md.",
        "rag_prefix":         "💡 На основі твого vault:\n",
        "rag_sources":        "\nДжерела:",
        "rag_not_found":      "🔍 Нічого не знайдено у vault за цим запитом.",
        "search_not_found":   'Нічого не знайдено для "{query}"',
        "search_found":       '🔍 Знайдено {count} нотаток для "{query}":\n',
        "index_building":     "⏳ Індекс будується — результати можуть бути неповними.",
        "search_degraded":    "⚠️ Семантичний пошук недоступний — використовую keyword пошук.",
        "reindex_start":      "⏳ Переіндексація vault…",
        "reindex_done":       "✅ Переіндексовано: {count} нотаток.",
        "mode_changed":       "✓ Режим змінено на: {mode}\n⚠️ Набере чинності після перезапуску бота.",
        "error_prefix":       "❌ Помилка: {error}",
        "ai_unavailable":     "❌ AI провайдер не відповідає. Перевірте що Ollama запущений та модель завантажена, або правильність API ключа.",
        "ai_not_ready":       "⚠️ BrainSync ще не готовий — AI не завантажився при старті. Перегляньте повідомлення про помилку, яке прийшло при запуску, і перезапустіть бота.",
        "duplicate_note":     "⚠️ Схожа нотатка вже існує:\n→ {path} ({pct}%)\n💡 Об'єднати? /merge",
        "related_note":       "💡 Можливо пов'язана нотатка:\n→ {path} ({pct}%)",
        "merge_no_pending":   "Немає незавершеного об'єднання. Спочатку збережіть нотатку — якщо виявлено дублікат, з'явиться /merge.",
        "merge_done":         "✅ Об'єднано у `{dest}`\nВидалено: `{src}`",
        "merge_failed":       "❌ Помилка об'єднання: {error}",
        "merge_files_gone":   "❌ Неможливо об'єднати: один із файлів більше не існує.",
    },
}

_SUPPORTED = set(STRINGS.keys())


def set_locale(locale: str) -> None:
    global _locale
    _locale = locale if locale in _SUPPORTED else "en"


def t(key: str, **kwargs) -> str:
    """Return the localised string for *key*, formatted with **kwargs."""
    lang = _SUPPORTED & {_locale} and _locale or "en"
    template = STRINGS.get(lang, STRINGS["en"]).get(key) or STRINGS["en"].get(key, key)
    return template.format(**kwargs) if kwargs else template
