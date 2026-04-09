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
        # Show confirmation dialog instead of merging immediately (#5)
        from telegram.handlers.commands import cmd_merge
        await cmd_merge(update, context)
        await query.edit_message_reply_markup(reply_markup=None)
        return

    # ── Merge confirmation ─────────────────────────────────────────────────────
    if data == "merge_do_confirm":
        from telegram.handlers.commands import _do_merge
        await _do_merge(update, context)
        return

    if data == "merge_do_cancel":
        context.user_data.pop("pending_merge", None)
        await query.edit_message_reply_markup(reply_markup=None)
        from telegram.i18n import t
        await query.message.reply_text(t("merge_cancelled"))
        return

    # ── Settings toggles ───────────────────────────────────────────────────────
    if data.startswith("settings:"):
        await _handle_settings(update, context, data[9:])
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


async def _handle_settings(
    update, context, sub: str
) -> None:
    """Handle settings:toggle:{key} and settings:close callbacks."""
    query = update.callback_query
    config = context.bot_data["config"]

    if sub == "close":
        await query.edit_message_reply_markup(reply_markup=None)
        return

    if not sub.startswith("toggle:"):
        return
    key = sub[7:]  # strip "toggle:"

    # Toggle the value in memory
    _TOGGLES = {
        "git.auto_commit":               ("git", "auto_commit"),
        "enrichment_add_wikilinks":      (None,  "enrichment_add_wikilinks"),
        "enrichment_update_moc":         (None,  "enrichment_update_moc"),
        "schedule.daily_summary_enabled": ("schedule", "daily_summary_enabled"),
    }
    if key not in _TOGGLES:
        await query.answer("Unknown setting.")
        return

    section, attr = _TOGGLES[key]
    obj = getattr(config, section) if section else config
    current = getattr(obj, attr)
    setattr(obj, attr, not current)
    new_val = not current

    # Persist to config.yaml
    try:
        _persist_setting(config.config_path, key, new_val)
    except Exception as exc:
        logger.warning("settings: persist failed: %s", exc)

    # Update the keyboard in place
    from telegram.keyboards import settings_keyboard
    from telegram.i18n import t
    await query.edit_message_reply_markup(reply_markup=settings_keyboard(config))
    await query.answer(t("settings_saved", key=key, value=new_val))


def _persist_setting(config_path: str, key: str, value: bool) -> None:
    """Write a single boolean toggle back to config.yaml."""
    import yaml
    from pathlib import Path

    p = Path(config_path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))

    # Map key → yaml path
    _YAML_PATH = {
        "git.auto_commit":               ["git", "auto_commit"],
        "enrichment_add_wikilinks":      ["enrichment", "add_wikilinks"],
        "enrichment_update_moc":         ["enrichment", "update_moc"],
        "schedule.daily_summary_enabled": ["schedule", "daily_summary", "enabled"],
    }
    parts = _YAML_PATH.get(key)
    if not parts:
        return

    node = raw
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value

    p.write_text(yaml.dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
