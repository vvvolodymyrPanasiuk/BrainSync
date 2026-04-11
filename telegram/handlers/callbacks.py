"""CallbackQueryHandler — handles all inline keyboard button presses."""
from __future__ import annotations

import logging
from datetime import time as _time

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# ── YAML key → config path mapping ───────────────────────────────────────────
_YAML_PATHS: dict[str, list[str]] = {
    "git.auto_commit":                 ["git", "auto_commit"],
    "enrichment_add_wikilinks":        ["enrichment", "add_wikilinks"],
    "enrichment_update_moc":           ["enrichment", "update_moc"],
    "schedule.daily_summary_enabled":  ["schedule", "daily_summary", "enabled"],
    "schedule.daily_summary_time":     ["schedule", "daily_summary", "time"],
    "schedule.weekly_review_enabled":  ["schedule", "weekly_review", "enabled"],
    "schedule.weekly_review_time":     ["schedule", "weekly_review", "time"],
    "schedule.monthly_review_enabled": ["schedule", "monthly_review", "enabled"],
    "schedule.monthly_review_time":    ["schedule", "monthly_review", "time"],
    "ai.provider":                     ["ai", "provider"],
    "ai.model":                        ["ai", "model"],
    "locale":                          ["locale"],
}

_BOOL_TOGGLES: dict[str, tuple[str | None, str]] = {
    "git.auto_commit":                 ("git",      "auto_commit"),
    "enrichment_add_wikilinks":        (None,       "enrichment_add_wikilinks"),
    "enrichment_update_moc":           (None,       "enrichment_update_moc"),
    "schedule.daily_summary_enabled":  ("schedule", "daily_summary_enabled"),
    "schedule.weekly_review_enabled":  ("schedule", "weekly_review_enabled"),
    "schedule.monthly_review_enabled": ("schedule", "monthly_review_enabled"),
}

_TEXT_PROMPTS: dict[str, str] = {
    "schedule.daily_summary_time":  "📅 Daily summary time — send HH:MM (e.g. 21:00):",
    "schedule.weekly_review_time":  "📅 Weekly review time — send HH:MM (e.g. 20:00):",
    "schedule.monthly_review_time": "📅 Monthly review time — send HH:MM (e.g. 10:00):",
    "ai.model":                     "🤖 Send the model name (e.g. claude-sonnet-4-6):",
}


def _setting_page(key: str) -> str:
    if key.startswith("schedule."): return "schedules"
    if key.startswith("ai."):       return "ai"
    if key == "locale":             return "language"
    return "notes"


def _persist_yaml(config_path: str, parts: list[str], value) -> None:
    import yaml
    from pathlib import Path
    p = Path(config_path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    node = raw
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value
    p.write_text(yaml.dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _apply_string_setting(config, key: str, value: str) -> None:
    if key == "ai.provider":
        config.ai.provider = value
    elif key == "ai.model":
        config.ai.model = value
    elif key == "locale":
        config.locale = value
        from telegram.i18n import set_locale
        set_locale(value)


async def _show_settings_page(query, config, page: str) -> None:
    from telegram.keyboards import (
        settings_main_keyboard, settings_notes_keyboard,
        settings_schedules_keyboard, settings_ai_keyboard,
        settings_language_keyboard,
    )
    from telegram.i18n import t

    _PAGES = {
        "main":      (lambda: settings_main_keyboard(),        "settings_header"),
        "notes":     (lambda: settings_notes_keyboard(config), "settings_notes_header"),
        "schedules": (lambda: settings_schedules_keyboard(config), "settings_schedules_header"),
        "ai":        (lambda: settings_ai_keyboard(config),    "settings_ai_header"),
        "language":  (lambda: settings_language_keyboard(config), "settings_language_header"),
    }
    if page not in _PAGES:
        page = "main"
    kb_fn, text_key = _PAGES[page]
    await query.edit_message_text(t(text_key), reply_markup=kb_fn(), parse_mode="Markdown")


# ── Main dispatcher ───────────────────────────────────────────────────────────

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

    # ── Settings ───────────────────────────────────────────────────────────────
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
            f"🏷️ Send tags (space-separated) for:\n`{file_path}`\n\nExample: `python async`",
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


# ── Settings handler ──────────────────────────────────────────────────────────

async def _handle_settings(update, context, sub: str) -> None:
    query = update.callback_query
    config = context.bot_data["config"]
    from telegram.i18n import t

    # Close
    if sub == "close":
        await query.edit_message_reply_markup(reply_markup=None)
        return

    # Page navigation
    if sub.startswith("page:"):
        page = sub[5:]
        await _show_settings_page(query, config, page)
        return

    # Toggle boolean setting
    if sub.startswith("toggle:"):
        key = sub[7:]
        if key not in _BOOL_TOGGLES:
            await query.answer("Unknown setting.")
            return
        section, attr = _BOOL_TOGGLES[key]
        obj = getattr(config, section) if section else config
        new_val = not getattr(obj, attr)
        setattr(obj, attr, new_val)
        _persist_yaml(config.config_path, _YAML_PATHS[key], new_val)
        await _show_settings_page(query, config, _setting_page(key))
        await query.answer(t("settings_saved", key=attr, value=new_val))
        return

    # Set string value (provider, locale)
    if sub.startswith("set:"):
        rest = sub[4:]
        key, value = rest.rsplit(":", 1)
        _apply_string_setting(config, key, value)
        _persist_yaml(config.config_path, _YAML_PATHS[key], value)
        await _show_settings_page(query, config, _setting_page(key))
        if key in ("ai.provider", "ai.model"):
            await query.answer("⚠️ Restart bot to apply AI changes")
        else:
            await query.answer("✅")
        return

    # Prompt user to type a value
    if sub.startswith("ask:"):
        key = sub[4:]
        context.user_data["pending_settings_input"] = key
        prompt = _TEXT_PROMPTS.get(key, "Send value:")
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(prompt)
        return


async def handle_settings_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Called from message handler when pending_settings_input is set.
    Returns True if the message was consumed.
    """
    key = context.user_data.get("pending_settings_input")
    if not key:
        return False

    context.user_data.pop("pending_settings_input", None)
    text = (update.message.text or "").strip()
    config = context.bot_data["config"]
    from telegram.i18n import t

    # Validate time format
    if key.endswith("_time"):
        import re
        if not re.match(r"^\d{2}:\d{2}$", text):
            await update.message.reply_text("❌ Invalid format. Use HH:MM (e.g. 21:00)")
            return True
        h, m = map(int, text.split(":"))
        if not (0 <= h <= 23 and 0 <= m <= 59):
            await update.message.reply_text("❌ Invalid time. Hours 00–23, minutes 00–59.")
            return True
        # Apply to in-memory config
        new_time = _time(h, m)
        _TIME_ATTRS = {
            "schedule.daily_summary_time":  ("schedule", "daily_summary_time"),
            "schedule.weekly_review_time":  ("schedule", "weekly_review_time"),
            "schedule.monthly_review_time": ("schedule", "monthly_review_time"),
        }
        section, attr = _TIME_ATTRS.get(key, (None, None))
        if section and attr:
            setattr(getattr(config, section), attr, new_time)
        _persist_yaml(config.config_path, _YAML_PATHS[key], text)
        await update.message.reply_text(
            f"✅ Time updated to {text}\n⚠️ Restart bot to reschedule jobs.",
        )
        return True

    # Model name (free text)
    if key == "ai.model":
        if not text:
            await update.message.reply_text("❌ Model name cannot be empty.")
            return True
        config.ai.model = text
        _persist_yaml(config.config_path, _YAML_PATHS[key], text)
        await update.message.reply_text(
            f"✅ Model set to `{text}`\n⚠️ Restart bot to apply.",
            parse_mode="Markdown",
        )
        return True

    return True
