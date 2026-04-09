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


def youtube_save_confirm() -> InlineKeyboardMarkup:
    """Confirm / edit / discard before saving YouTube session."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Save",         callback_data="yt_save_confirm"),
        InlineKeyboardButton("✏️ Edit first",   callback_data="yt_save_edit"),
        InlineKeyboardButton("❌ Discard",      callback_data="yt_end"),
    ]])
