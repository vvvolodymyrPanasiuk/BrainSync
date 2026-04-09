"""InlineKeyboardMarkup builders for all bot interactions."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def save_actions(file_path: str) -> InlineKeyboardMarkup:
    """Shown after a note is saved."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📁 Move", callback_data=f"move:{file_path}"),
        InlineKeyboardButton("🏷️ Tags",  callback_data=f"tags:{file_path}"),
    ]])


def duplicate_actions() -> InlineKeyboardMarkup:
    """Shown when a similar note (≥ 0.85) is detected."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔀 Merge",      callback_data="dup_merge"),
        InlineKeyboardButton("✅ Keep both",  callback_data="dup_keep"),
    ]])


def youtube_chat_actions() -> InlineKeyboardMarkup:
    """Persistent action bar during an active YouTube session."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("💾 Save to vault", callback_data="yt_save"),
        InlineKeyboardButton("❌ End session",   callback_data="yt_end"),
    ]])


def merge_confirm_keyboard() -> InlineKeyboardMarkup:
    """Confirmation dialog before merging notes."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirm merge", callback_data="merge_do_confirm"),
        InlineKeyboardButton("❌ Cancel",        callback_data="merge_do_cancel"),
    ]])


def settings_keyboard(config) -> InlineKeyboardMarkup:
    """Inline keyboard for toggling key bot settings."""
    def _flag(val: bool) -> str:
        return "✅" if val else "❌"

    rows = [
        [InlineKeyboardButton(
            f"{_flag(config.git.auto_commit)} Auto-commit",
            callback_data="settings:toggle:git.auto_commit",
        )],
        [InlineKeyboardButton(
            f"{_flag(config.enrichment_add_wikilinks)} Wikilinks",
            callback_data="settings:toggle:enrichment_add_wikilinks",
        ),
        InlineKeyboardButton(
            f"{_flag(config.enrichment_update_moc)} MoC",
            callback_data="settings:toggle:enrichment_update_moc",
        )],
        [InlineKeyboardButton(
            f"{_flag(config.schedule.daily_summary_enabled)} Daily summary",
            callback_data="settings:toggle:schedule.daily_summary_enabled",
        )],
        [InlineKeyboardButton("✖️ Close", callback_data="settings:close")],
    ]
    return InlineKeyboardMarkup(rows)


def youtube_save_confirm() -> InlineKeyboardMarkup:
    """Confirm / edit / discard before saving YouTube session."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Save",         callback_data="yt_save_confirm"),
        InlineKeyboardButton("✏️ Edit first",   callback_data="yt_save_edit"),
        InlineKeyboardButton("❌ Discard",      callback_data="yt_end"),
    ]])
