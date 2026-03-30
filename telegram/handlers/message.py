"""Telegram plain-text message handler with prefix detection and rate-limit retry."""
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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route plain-text Telegram message: auth → typing → prefix detect → save → reply."""
    from telegram.handlers.commands import auth_check
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return

    text = update.message.text or ""
    if not text.strip():
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    # Detect inline prefix (нотатка:, task:, etc.)
    note_type, clean_text = detect_prefix(text, config.prefixes)

    index = context.bot_data["index"]
    stats = context.bot_data["stats"]
    provider = context.bot_data.get("provider")

    result = await _run_create_note(clean_text, note_type, None, config, index, stats, provider)

    if result.get("success"):
        from telegram.formatter import format_confirmation
        reply = format_confirmation(result["file_path"])
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
) -> dict:
    """Run handle_create_note in executor (blocking file I/O + AI calls)."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        handle_create_note,
        text, note_type, folder, config, index, stats, provider,
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
                from telegram.formatter import format_ai_fallback
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
