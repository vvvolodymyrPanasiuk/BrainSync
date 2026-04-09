"""CallbackQueryHandler — handles all inline keyboard button presses."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data: str = query.data or ""

    # ── Duplicate-note actions ─────────────────────────────────────────────────
    if data == "dup_keep":
        context.user_data.pop("pending_merge", None)
        await query.edit_message_reply_markup(reply_markup=None)
        return

    if data == "dup_merge":
        from telegram.handlers.commands import cmd_merge
        await cmd_merge(update, context)
        await query.edit_message_reply_markup(reply_markup=None)
        return

    # ── Post-save actions ──────────────────────────────────────────────────────
    if data.startswith("move:"):
        file_path = data[5:]
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"📁 Send destination folder for:\n`{file_path}`\n\nExample: `Finance/Trading`",
            parse_mode="Markdown",
        )
        context.user_data["pending_move_path"] = file_path
        return

    if data.startswith("tags:"):
        file_path = data[5:]
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"🏷️ Send tags to add (space-separated) for:\n`{file_path}`\n\nExample: `python async`",
            parse_mode="Markdown",
        )
        context.user_data["pending_tags_path"] = file_path
        return

    # ── YouTube session actions ────────────────────────────────────────────────
    if data == "yt_save":
        from telegram.handlers.youtube_chat import preview_save
        await query.edit_message_reply_markup(reply_markup=None)
        await preview_save(update, context)
        return

    if data == "yt_save_confirm":
        from telegram.handlers.youtube_chat import confirm_save
        await confirm_save(update, context)
        return

    if data == "yt_save_edit":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "✏️ Send your edited note content and I'll save it to the vault."
        )
        context.user_data["yt_waiting_edit"] = True
        return

    if data == "yt_end":
        from telegram.handlers.youtube_chat import end_session
        await end_session(update, context)
        return

    logger.debug("callbacks: unhandled data=%r", data)
