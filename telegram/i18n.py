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
        "duplicate_note":     "⚠️ Similar note already exists:\n→ {path} ({pct}%)",
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
        "settings_header":          "⚙️ *BrainSync Settings*\n\nChoose a section:",
        "settings_notes_header":    "📝 *Notes*\n\nToggle note enrichment options:",
        "settings_schedules_header": "📅 *Schedules*\n\nToggle reports and set their times.\nTime changes take effect after restart.",
        "settings_ai_header":       "🤖 *AI Provider*\n\nSelect provider and model.\nChanges take effect after restart.",
        "settings_language_header": "🌐 *Language*\n\nChoose bot interface language:",
        "settings_saved":     "✅ Setting updated: `{key}` → `{value}`",
        "stats_header":       "📊 *Vault Statistics*",
        "gaps_thinking":      "🔍 Analyzing knowledge gaps…",
        "gaps_header":        "🧩 *Knowledge gaps for: {topic}*\n\n",
        "gaps_no_ai":         "❌ AI provider required for gap analysis.",
        "graph_building":     "🕸️ Building knowledge graph…",
        "graph_no_lib":       "❌ Install `networkx` and `matplotlib`:\n```\npip install networkx matplotlib\n```",
        "graph_empty":        "ℹ️ No wikilinks found in vault yet.",
        "clip_summarising":   "🤖 Summarising with AI…",
        "progress_thinking":      "⏳ Thinking…",
        "vault_search_progress":    "🔍 Searching your vault…",
        "web_search_progress":     "🌐 Searching the web…",
        "combined_search_progress": "🔍🌐 Searching vault and web…",
        "chat_web_disclaimer":    "_ℹ️ General answer — Claude Code may have used web search. Use `?` to search only your vault._",
        "insight_novel_save":  "💡 Save synthesis to vault",
        "lint_stale_header":   "🕰 *Stale notes* ({count}) — older than 180 days:\n",
        "lint_contra_none":    "✅ No contradictions found between notes.",
        "lint_contra_header":  "⚠️ *{count} contradiction(s) found:*\n",
        "index_rebuilt":       "📑 vault/index.md rebuilt ({total} notes).",
        "synthesis_done":      "🔄 Topic synthesis updated: {topic}",
        "help_text": (
            "📋 *BrainSync commands*\n\n"
            "Just send a message — AI will classify and save it automatically.\n"
            "Plain questions: vault checked first (📚), then AI answer (🤖).\n\n"
            "*Search shortcuts:*\n"
            "`? <query>` — search *only your vault* (hybrid BM25+vector)\n"
            "`?? <query>` — AI *web search* for current data\n"
            "`??? <query>` — vault *and* web, both labeled sections\n\n"
            "*Note type prefixes:*\n"
            "`note:` `task:` `idea:` `journal:` — force a note type\n\n"
            "*Commands:*\n"
            "`/clip <url>` — fetch & summarise a web page\n"
            "`/today` — today's notes + open tasks\n"
            "`/stats` — vault statistics with charts\n"
            "`/lint` — vault health check + fix actions (LLM-Wiki lint)\n"
            "`/notebooklm` — generate presentations, podcasts, slides from vault notes\n"
            "`/settings` — toggle auto-commit, wikilinks, MoC, summaries\n"
            "`/status` — bot status & AI provider info\n"
            "`/reload` — hot-reload config without restart\n"
            "`/reindex` — rebuild vector index + global index.md\n"
            "`/compact` — summarise & clear conversation context\n"
            "`/newchat` — hard reset conversation context\n"
            "`/help` — this message\n"
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
        "duplicate_note":     "⚠️ Схожа нотатка вже існує:\n→ {path} ({pct}%)",
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
        "settings_header":          "⚙️ *Налаштування BrainSync*\n\nОберіть розділ:",
        "settings_notes_header":    "📝 *Нотатки*\n\nОпції збагачення нотаток:",
        "settings_schedules_header": "📅 *Звіти*\n\nВмикайте звіти та налаштовуйте час.\nЗміна часу набере чинності після перезапуску.",
        "settings_ai_header":       "🤖 *AI провайдер*\n\nОберіть провайдера та модель.\nЗміни набудуть чинності після перезапуску.",
        "settings_language_header": "🌐 *Мова*\n\nОберіть мову інтерфейсу бота:",
        "settings_saved":     "✅ Налаштування оновлено: `{key}` → `{value}`",
        "stats_header":       "📊 *Статистика Vault*",
        "gaps_thinking":      "🔍 Аналізую прогалини знань…",
        "gaps_header":        "🧩 *Прогалини знань для: {topic}*\n\n",
        "gaps_no_ai":         "❌ Потрібен AI провайдер для аналізу прогалин.",
        "graph_building":     "🕸️ Будую граф знань…",
        "graph_no_lib":       "❌ Встановіть `networkx` та `matplotlib`:\n```\npip install networkx matplotlib\n```",
        "graph_empty":        "ℹ️ Поки що немає вікіпосилань у vault.",
        "clip_summarising":   "🤖 Узагальнюю за допомогою AI…",
        "progress_thinking":      "⏳ Думаю…",
        "vault_search_progress":    "🔍 Шукаю у vault…",
        "web_search_progress":     "🌐 Шукаю в інтернеті…",
        "combined_search_progress": "🔍🌐 Шукаю у vault та в інтернеті…",
        "chat_web_disclaimer":    "_ℹ️ Загальна відповідь — Claude Code міг використати пошук в інтернеті. Щоб шукати лише у vault, використай `?`._",
        "insight_novel_save":  "💡 Зберегти синтез у vault",
        "lint_stale_header":   "🕰 *Застарілі нотатки* ({count}) — старші 180 днів:\n",
        "lint_contra_none":    "✅ Суперечностей між нотатками не знайдено.",
        "lint_contra_header":  "⚠️ *Знайдено {count} суперечностей:*\n",
        "index_rebuilt":       "📑 vault/index.md оновлено ({total} нотаток).",
        "synthesis_done":      "🔄 Синтез теми оновлено: {topic}",
        "help_text": (
            "📋 *Команди BrainSync*\n\n"
            "Просто надішли повідомлення — AI автоматично класифікує та збереже його.\n"
            "Звичайні запитання: спочатку перевіряється vault (📚), потім відповідь ШІ (🤖).\n\n"
            "*Шорткати пошуку:*\n"
            "`? <запит>` — шукати *тільки у vault* (гібридний BM25+vector)\n"
            "`?? <запит>` — ШІ *шукає в інтернеті* актуальні дані\n"
            "`??? <запит>` — vault *і* інтернет, обидві секції із позначками\n\n"
            "*Префікси типу нотатки:*\n"
            "`нотатка:` `задача:` `ідея:` `день:` — задати тип без AI-роутера\n\n"
            "*Команди:*\n"
            "`/clip <url>` — завантажити та узагальнити веб-сторінку\n"
            "`/today` — нотатки за сьогодні + відкриті завдання\n"
            "`/stats` — статистика vault із графіками\n"
            "`/lint` — перевірка vault + кнопки виправлення (LLM-Wiki lint)\n"
            "`/notebooklm` — генерувати презентації, подкасти, слайди з нотаток\n"
            "`/settings` — перемкнути auto-commit, wikilinks, MoC, дайджест\n"
            "`/status` — статус бота та AI провайдера\n"
            "`/reload` — перезавантажити config без перезапуску\n"
            "`/reindex` — перебудувати індекс пошуку + index.md\n"
            "`/compact` — узагальнити та очистити контекст розмови\n"
            "`/newchat` — повне скидання контексту розмови\n"
            "`/help` — це повідомлення\n"
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
