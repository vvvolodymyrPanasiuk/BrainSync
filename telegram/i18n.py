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
        "clip_saved":         "📎 Clipped → `{file_path}`\n_Source: {url}_",
        "clip_error":         "❌ Could not clip URL: {error}",
        "clip_fetching":      "⏳ Fetching and clipping…",
        "split_saved":        "📝 Split into {count} notes:",
        "merge_confirm":      "⚠️ Merge confirmation:\n• New: `{new}`\n• Into: `{dup}`\n\nThe new note will be deleted. Confirm?",
        "merge_cancelled":    "❌ Merge cancelled.",
        "settings_header":    "⚙️ *BrainSync Settings*\n\nTap a button to toggle:",
        "settings_saved":     "✅ Setting updated: `{key}` → `{value}`",
        "stats_header":       "📊 *Vault Statistics*",
        "gaps_thinking":      "🔍 Analyzing knowledge gaps…",
        "gaps_header":        "🧩 *Knowledge gaps for: {topic}*\n\n",
        "gaps_no_ai":         "❌ AI provider required for gap analysis.",
        "graph_building":     "🕸️ Building knowledge graph…",
        "graph_no_lib":       "❌ Install `networkx` and `matplotlib`:\n```\npip install networkx matplotlib\n```",
        "graph_empty":        "ℹ️ No wikilinks found in vault yet.",
        "clip_summarising":   "🤖 Summarising with AI…",
        "progress_thinking":  "⏳ Thinking…",
        "help_text": (
            "📋 *BrainSync commands*\n\n"
            "*Notes*\n"
            "`/note <text>` — save a note\n"
            "`/task <text>` — save a task\n"
            "`/idea <text>` — save an idea\n"
            "`/journal <text>` — save a journal entry\n"
            "`/clip <url>` — fetch & summarise a web page\n"
            "YouTube URL — interactive Q&A via NotebookLM\n\n"
            "*Vault*\n"
            "`/search <query>` — semantic vault search\n"
            "`/today` — today's notes + all open tasks\n"
            "`/stats` — vault statistics with charts\n"
            "`/graph` — knowledge graph PNG\n"
            "`/gaps <topic>` — find missing subtopics in your vault\n"
            "`/health` — vault health check (orphans, broken links)\n"
            "`/move <topic> -> <folder>` — move a note\n"
            "`/merge` — merge note with detected duplicate\n\n"
            "*Groups*\n"
            "`/registertopic <Folder>` — map Telegram thread to vault folder\n\n"
            "*System*\n"
            "`/settings` — toggle auto-commit, wikilinks, MoC, daily summary\n"
            "`/status` — bot status, session stats, AI provider info\n"
            "`/reload` — hot-reload config.yaml without restart\n"
            "`/reindex` — rebuild vector search index\n"
            "`/help` — this message\n\n"
            "_You can also just send a plain message — AI will classify and save it automatically._"
        ),
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
        "clip_saved":         "📎 Збережено → `{file_path}`\n_Джерело: {url}_",
        "clip_error":         "❌ Не вдалося завантажити URL: {error}",
        "clip_fetching":      "⏳ Завантажую та зберігаю…",
        "split_saved":        "📝 Розбито на {count} нотатки:",
        "merge_confirm":      "⚠️ Підтвердження об'єднання:\n• Нова: `{new}`\n• У: `{dup}`\n\nНову нотатку буде видалено. Підтвердити?",
        "merge_cancelled":    "❌ Об'єднання скасовано.",
        "settings_header":    "⚙️ *Налаштування BrainSync*\n\nНатисніть кнопку для зміни:",
        "settings_saved":     "✅ Налаштування оновлено: `{key}` → `{value}`",
        "stats_header":       "📊 *Статистика Vault*",
        "gaps_thinking":      "🔍 Аналізую прогалини знань…",
        "gaps_header":        "🧩 *Прогалини знань для: {topic}*\n\n",
        "gaps_no_ai":         "❌ Потрібен AI провайдер для аналізу прогалин.",
        "graph_building":     "🕸️ Будую граф знань…",
        "graph_no_lib":       "❌ Встановіть `networkx` та `matplotlib`:\n```\npip install networkx matplotlib\n```",
        "graph_empty":        "ℹ️ Поки що немає вікіпосилань у vault.",
        "clip_summarising":   "🤖 Узагальнюю за допомогою AI…",
        "progress_thinking":  "⏳ Думаю…",
        "help_text": (
            "📋 *Команди BrainSync*\n\n"
            "*Нотатки*\n"
            "`/note <текст>` — зберегти нотатку\n"
            "`/task <текст>` — зберегти завдання\n"
            "`/idea <текст>` — зберегти ідею\n"
            "`/journal <текст>` — зберегти запис у щоденник\n"
            "`/clip <url>` — завантажити та узагальнити веб-сторінку\n"
            "YouTube URL — інтерактивні Q&A через NotebookLM\n\n"
            "*Vault*\n"
            "`/search <запит>` — семантичний пошук по vault\n"
            "`/today` — нотатки за сьогодні + всі відкриті завдання\n"
            "`/stats` — статистика vault із графіками\n"
            "`/graph` — граф знань (PNG)\n"
            "`/gaps <тема>` — аналіз прогалин у знаннях\n"
            "`/health` — перевірка vault (сироти, зламані посилання)\n"
            "`/move <тема> -> <папка>` — перемістити нотатку\n"
            "`/merge` — об'єднати нотатку з виявленим дублікатом\n\n"
            "*Групи*\n"
            "`/registertopic <Папка>` — прив'язати топік Telegram до папки vault\n\n"
            "*Система*\n"
            "`/settings` — перемкнути auto-commit, wikilinks, MoC, daily summary\n"
            "`/status` — статус бота, статистика сесії, інфо про AI\n"
            "`/reload` — перезавантажити config.yaml без перезапуску\n"
            "`/reindex` — перебудувати індекс семантичного пошуку\n"
            "`/help` — це повідомлення\n\n"
            "_Можна також просто надіслати звичайне повідомлення — AI автоматично класифікує та збереже його._"
        ),
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
