"""Telegram plain-text message handler: AI semantic routing via ActionPlan."""
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
    """Route plain-text Telegram message: auth → AI semantic router → executor."""
    from telegram.handlers.commands import auth_check
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return

    text = update.message.text or ""
    if not text.strip():
        return

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )

    provider    = context.bot_data.get("provider")
    vector_store = context.bot_data.get("vector_store")
    index        = context.bot_data["index"]
    stats        = context.bot_data["stats"]

    # ── Prefix detection (explicit type overrides AI routing) ─────────────────
    note_type, clean_text = detect_prefix(text, config.prefixes)
    if note_type is not None:
        # User explicitly typed a prefix (e.g., "задача: ...") — bypass router
        result = await _run_create_note(
            clean_text, note_type, None, config, index, stats, provider, vector_store
        )
        reply = _format_save_result(result, config)
        await _reply_with_retry(update, reply)
        if result.get("success") and config.git.enabled and config.git.auto_commit:
            _git_commit(result["file_path"], config)
        return

    # ── AI required ───────────────────────────────────────────────────────────
    if not context.bot_data.get("ai_ready", False):
        from telegram.i18n import t
        await _reply_with_retry(update, t("ai_not_ready"))
        return

    # ── AI Semantic Router ────────────────────────────────────────────────────
    try:
        plan = await _route(text, provider, index, config.vault.language)
    except Exception as exc:
        logger.error("routing failed: %s", exc, exc_info=True)
        await _reply_with_retry(update, f"❌ AI error: `{exc}`")
        return

    # ── Executor ──────────────────────────────────────────────────────────────
    from vault_writer.tools.executor import execute
    reply = await execute(
        plan=plan,
        message=text,
        update=update,
        context=context,
        config=config,
        index=index,
        stats=stats,
        provider=provider,
        vector_store=vector_store,
    )

    if reply:
        await _reply_with_retry(update, reply)

    # Git commit if a note was saved
    if plan.should_save and stats.last_note_path and config.git.enabled and config.git.auto_commit:
        _git_commit(stats.last_note_path, config)


# ── Routing ───────────────────────────────────────────────────────────────────

async def _route(text: str, provider, index, locale: str = "en") -> object:
    """Run AI router in executor. Raises on failure — caller handles the error."""
    from vault_writer.ai.router import route
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, route, text, provider, index, locale)


# ── Legacy note creation (used by prefix path and /commands) ─────────────────

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
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        handle_create_note,
        text, note_type, folder, config, index, stats, provider, vector_store,
    )


def _format_save_result(result: dict, config) -> str:
    if result.get("success"):
        from telegram.formatter import format_confirmation, format_similarity_notice
        reply = format_confirmation(result["file_path"])
        notices = result.get("similarity_notices", [])
        if notices:
            reply += "\n\n" + format_similarity_notice(notices)
        return reply
    return f"❌ Помилка: {result.get('error', 'невідома помилка')}"


# ── Retry helper ──────────────────────────────────────────────────────────────

async def _reply_with_retry(update: Update, text: str, max_attempts: int = 3) -> None:
    """Send reply with exponential backoff on RetryAfter errors."""
    from telegram.constants import ParseMode
    for attempt in range(max_attempts):
        try:
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
            return
        except RetryAfter as exc:
            wait = exc.retry_after if attempt < max_attempts - 1 else None
            if wait is None:
                await update.message.reply_text(
                    "⚠️ Telegram API тимчасово недоступний."
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
