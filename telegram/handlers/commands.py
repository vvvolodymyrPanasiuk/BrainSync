"""Telegram slash command handlers."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from vault_writer.vault.writer import NoteType

logger = logging.getLogger(__name__)


def auth_check(update: Update, config) -> bool:
    """Return False and log warning if user is not in allowed_user_ids."""
    user_id = update.effective_user.id if update.effective_user else None
    if user_id not in config.telegram.allowed_user_ids:
        logger.warning("Unauthorized access attempt: user_id=%s", user_id)
        return False
    return True


async def cmd_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Використання: /note <текст>")
        return
    await _save_with_type(update, context, text, NoteType.NOTE)


async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Використання: /task <текст>")
        return
    await _save_with_type(update, context, text, NoteType.TASK)


async def cmd_idea(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Використання: /idea <текст>")
        return
    await _save_with_type(update, context, text, NoteType.IDEA)


async def cmd_journal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Використання: /journal <текст>")
        return
    await _save_with_type(update, context, text, NoteType.JOURNAL)


async def _save_with_type(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, note_type: NoteType) -> None:
    from telegram.constants import ChatAction
    from vault_writer.tools.create_note import handle_create_note
    from telegram.handlers.message import _run_create_note

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    config = context.bot_data["config"]
    index = context.bot_data["index"]
    stats = context.bot_data["stats"]
    provider = context.bot_data.get("provider")

    result = await _run_create_note(text, note_type, None, config, index, stats, provider)
    reply = _format_result(result, config)
    await update.message.reply_text(reply)

    # Git commit
    if result.get("success") and config.git.enabled and config.git.auto_commit:
        _git_commit(result["file_path"], config)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return
    help_text = (
        "📋 BrainSync команди:\n\n"
        "/note <текст> — зберегти нотатку\n"
        "/task <текст> — зберегти задачу\n"
        "/idea <текст> — зберегти ідею\n"
        "/journal <текст> — запис у щоденник\n"
        "/search <запит> — пошук у vault\n"
        "/mode minimal|balanced|full — змінити режим\n"
        "/status — статус бота\n"
        "/help — ця довідка"
    )
    await update.message.reply_text(help_text)


async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return
    mode = context.args[0].lower() if context.args else ""
    if mode not in ("minimal", "balanced", "full"):
        await update.message.reply_text("Режим: minimal | balanced | full")
        return
    try:
        from config.loader import update_processing_mode
        update_processing_mode(config.config_path, mode)
        from telegram.formatter import format_mode_confirmation
        await update.message.reply_text(format_mode_confirmation(mode))
    except Exception as exc:
        logger.error("cmd_mode error: %s", exc)
        await update.message.reply_text(f"❌ Помилка зміни режиму: {exc}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return
    index = context.bot_data["index"]
    stats = context.bot_data["stats"]
    from telegram.formatter import format_status
    await update.message.reply_text(format_status(config, stats, index))


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("Використання: /search <запит>")
        return
    from vault_writer.tools.search_notes import handle_search_notes
    index = context.bot_data["index"]
    result = handle_search_notes(query=query, limit=10, folder=None, index=index, vault_path=config.vault.path)
    from telegram.formatter import format_search_results
    await update.message.reply_text(format_search_results(result.get("results", []), query))


def _format_result(result: dict, config) -> str:
    if result.get("success"):
        from telegram.formatter import format_confirmation
        return format_confirmation(result["file_path"])
    return f"❌ Помилка: {result.get('error', 'невідома помилка')}"


def _git_commit(file_path: str, config) -> None:
    try:
        from git_sync.sync import commit_note
        commit_note(config.vault.path, file_path, config.git)
    except Exception as exc:
        logger.warning("git commit error: %s", exc)
