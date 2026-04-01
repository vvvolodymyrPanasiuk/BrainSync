"""Telegram plain-text message handler with intent routing and prefix detection."""
from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.error import RetryAfter
from telegram.ext import ContextTypes

from vault_writer.tools.create_note import detect_prefix, handle_create_note
from vault_writer.vault.writer import NoteType

logger = logging.getLogger(__name__)

# Warning suppressed once per session to avoid log spam
_INTENT_WARN_ISSUED = False


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route plain-text Telegram message: auth → intent classify → RAG/search/save."""
    from telegram.handlers.commands import auth_check
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return

    text = update.message.text or ""
    if not text.strip():
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    provider = context.bot_data.get("provider")
    vector_store = context.bot_data.get("vector_store")

    # ── Intent classification ─────────────────────────────────────────────────
    if provider is not None and vector_store is not None:
        intent = await _classify_intent_safe(text, provider)
    else:
        from vault_writer.rag.intent import IntentType
        intent = IntentType.NEW_NOTE

    from vault_writer.rag.intent import IntentType

    # ── RAG query ────────────────────────────────────────────────────────────
    if intent == IntentType.RAG_QUERY and vector_store is not None:
        await _handle_rag_query(text, update, context, vector_store, provider, config)
        return

    # ── Search query ─────────────────────────────────────────────────────────
    if intent == IntentType.SEARCH_QUERY and vector_store is not None:
        await _handle_search_query(text, update, context, vector_store, config)
        return

    # ── Chat (casual / general AI question — do not save) ────────────────────
    if intent == IntentType.CHAT:
        await _handle_chat(text, update, provider)
        return

    # ── New note (default) ───────────────────────────────────────────────────
    await _handle_new_note(text, update, context, config, vector_store)


async def _classify_intent_safe(text: str, provider) -> object:
    """Classify intent in executor; returns NEW_NOTE on any error."""
    global _INTENT_WARN_ISSUED
    from vault_writer.rag.intent import IntentType, classify_intent
    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, classify_intent, text, provider)
    except (RuntimeError, ImportError) as exc:
        if not _INTENT_WARN_ISSUED:
            logger.warning("Intent classification unavailable (%s) — defaulting to new_note", exc)
            _INTENT_WARN_ISSUED = True
        return IntentType.NEW_NOTE


async def _handle_rag_query(text, update, context, vector_store, provider, config) -> None:
    from vault_writer.rag.engine import answer_query
    from telegram.formatter import (
        format_index_building_notice, format_rag_answer, format_rag_not_found,
    )

    prefix = ""
    if getattr(vector_store, "_building", False):
        prefix = format_index_building_notice() + "\n\n"

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, answer_query, text, vector_store, provider, config.embedding.top_k_results, config
    )

    if result.found:
        reply = prefix + format_rag_answer(result.answer, result.sources)
    else:
        reply = prefix + format_rag_not_found()

    await _reply_with_retry(update, reply)


async def _handle_search_query(text, update, context, vector_store, config) -> None:
    from vault_writer.rag.engine import search_vault
    from telegram.formatter import format_index_building_notice, format_semantic_search_results

    prefix = ""
    if getattr(vector_store, "_building", False):
        prefix = format_index_building_notice() + "\n\n"

    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(
        None, search_vault, text, vector_store, config.embedding.top_k_results
    )
    reply = prefix + format_semantic_search_results(results, text)
    await _reply_with_retry(update, reply)


async def _handle_chat(text: str, update, provider) -> None:
    """Respond to casual chat / general AI questions without saving to vault."""
    from telegram.formatter import format_chat_reply
    from telegram.i18n import t
    if provider is not None:
        prompt = f"Respond in the same language as the user's message.\n\nUser: {text}"
        loop = asyncio.get_running_loop()
        answer = await loop.run_in_executor(None, provider.complete, prompt)
        reply = format_chat_reply(answer)
    else:
        reply = t("ai_unavailable")
    await _reply_with_retry(update, reply)


async def _handle_new_note(text, update, context, config, vector_store) -> None:
    note_type, clean_text = detect_prefix(text, config.prefixes)
    index = context.bot_data["index"]
    stats = context.bot_data["stats"]
    provider = context.bot_data.get("provider")

    result = await _run_create_note(
        clean_text, note_type, None, config, index, stats, provider, vector_store
    )

    if result.get("success"):
        from telegram.formatter import format_confirmation, format_similarity_notice
        reply = format_confirmation(result["file_path"])
        notices = result.get("similarity_notices", [])
        if notices:
            reply += "\n\n" + format_similarity_notice(notices)
        if config.git.enabled and config.git.auto_commit:
            _git_commit(result["file_path"], config)
    else:
        reply = f"❌ Помилка: {result.get('error', 'невідома помилка')}"

    await _reply_with_retry(update, reply)


async def _run_create_note(
    text: str,
    note_type: NoteType | None,
    folder: str | None,
    config,
    index,
    stats,
    provider,
    vector_store=None,
) -> dict:
    """Run handle_create_note in executor (blocking file I/O + AI calls)."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        handle_create_note,
        text, note_type, folder, config, index, stats, provider, vector_store,
    )


async def _reply_with_retry(update: Update, text: str, max_attempts: int = 3) -> None:
    """Send reply with exponential backoff on RetryAfter errors."""
    for attempt in range(max_attempts):
        try:
            await update.message.reply_text(text)
            return
        except RetryAfter as exc:
            wait = exc.retry_after if attempt < max_attempts - 1 else None
            if wait is None:
                await update.message.reply_text(
                    "⚠️ Telegram API тимчасово недоступний. Спробую ще раз пізніше."
                )
                return
            logger.warning("RetryAfter: waiting %ss (attempt %d)", wait, attempt + 1)
            await asyncio.sleep(wait)
        except Exception as exc:
            logger.error("reply_text failed: %s", exc)
            return


def _git_commit(file_path: str, config) -> None:
    try:
        from git_sync.sync import commit_note
        commit_note(config.vault.path, file_path, config.git)
    except Exception as exc:
        logger.warning("git commit error: %s", exc)
