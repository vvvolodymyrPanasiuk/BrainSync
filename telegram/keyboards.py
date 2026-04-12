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


def lint_actions_keyboard(
    topics_no_moc: list,
    isolated: list,
    orphans: list,
    stale: list | None = None,
) -> InlineKeyboardMarkup | None:
    """Action buttons shown below lint report — only for fixable issues."""
    rows = []
    row1 = []
    if topics_no_moc:
        row1.append(InlineKeyboardButton(
            f"✅ Створити MoC ({len(topics_no_moc)})",
            callback_data="lint_create_moc",
        ))
    if isolated:
        row1.append(InlineKeyboardButton(
            f"🔗 Додати links ({len(isolated)})",
            callback_data="lint_enrich_isolated",
        ))
    if row1:
        rows.append(row1)

    row2 = []
    if orphans:
        row2.append(InlineKeyboardButton(
            f"👁 Показати orphans ({len(orphans)})",
            callback_data="lint_show_orphans",
        ))
    if stale:
        row2.append(InlineKeyboardButton(
            f"🕰 Застарілі ({len(stale)})",
            callback_data="lint_show_stale",
        ))
    if row2:
        rows.append(row2)

    # Contradiction scan is always offered (AI-powered, on demand)
    rows.append([InlineKeyboardButton(
        "⚠️ Знайти суперечності (AI)",
        callback_data="lint_contradictions",
    )])

    return InlineKeyboardMarkup(rows) if rows else None


def save_insight_keyboard() -> InlineKeyboardMarkup:
    """Shown after a RAG/chat answer — lets user save it as a vault note."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("💡 Зберегти як нотатку", callback_data="insight_save"),
        InlineKeyboardButton("✖️ Скасувати",            callback_data="insight_discard"),
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


def youtube_save_confirm() -> InlineKeyboardMarkup:
    """Confirm / edit / discard before saving YouTube session."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Save",         callback_data="yt_save_confirm"),
        InlineKeyboardButton("✏️ Edit first",   callback_data="yt_save_edit"),
        InlineKeyboardButton("❌ Discard",      callback_data="yt_end"),
    ]])


# ── Settings keyboards ────────────────────────────────────────────────────────

def settings_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝 Notes",     callback_data="settings:page:notes"),
            InlineKeyboardButton("📅 Schedules", callback_data="settings:page:schedules"),
        ],
        [
            InlineKeyboardButton("🤖 AI",        callback_data="settings:page:ai"),
            InlineKeyboardButton("🌐 Language",  callback_data="settings:page:language"),
        ],
        [InlineKeyboardButton("✖️ Close", callback_data="settings:close")],
    ])


def settings_notes_keyboard(config) -> InlineKeyboardMarkup:
    def _f(v: bool) -> str:
        return "✅" if v else "❌"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"{_f(config.git.auto_commit)} Auto-commit git",
            callback_data="settings:toggle:git.auto_commit",
        )],
        [
            InlineKeyboardButton(
                f"{_f(config.enrichment_add_wikilinks)} Wikilinks",
                callback_data="settings:toggle:enrichment_add_wikilinks",
            ),
            InlineKeyboardButton(
                f"{_f(config.enrichment_update_moc)} MoC",
                callback_data="settings:toggle:enrichment_update_moc",
            ),
        ],
        [InlineKeyboardButton("← Back", callback_data="settings:page:main")],
    ])


def settings_schedules_keyboard(config) -> InlineKeyboardMarkup:
    def _f(v: bool) -> str:
        return "✅" if v else "❌"

    s = config.schedule
    daily_t  = s.daily_summary_time.strftime("%H:%M")
    weekly_t = s.weekly_review_time.strftime("%H:%M")
    monthly_t = s.monthly_review_time.strftime("%H:%M")

    _DAY_ABBR = {
        "monday": "Mon", "tuesday": "Tue", "wednesday": "Wed",
        "thursday": "Thu", "friday": "Fri", "saturday": "Sat", "sunday": "Sun",
    }
    day_abbr = _DAY_ABBR.get(s.weekly_review_day.lower(), s.weekly_review_day[:3])

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"{_f(s.daily_summary_enabled)} Daily  {daily_t}",
                callback_data="settings:toggle:schedule.daily_summary_enabled",
            ),
            InlineKeyboardButton("✏️ time", callback_data="settings:ask:schedule.daily_summary_time"),
        ],
        [
            InlineKeyboardButton(
                f"{_f(s.weekly_review_enabled)} Weekly  {day_abbr} {weekly_t}",
                callback_data="settings:toggle:schedule.weekly_review_enabled",
            ),
            InlineKeyboardButton("✏️ time", callback_data="settings:ask:schedule.weekly_review_time"),
        ],
        [
            InlineKeyboardButton(
                f"{_f(s.monthly_review_enabled)} Monthly  {s.monthly_review_day}th {monthly_t}",
                callback_data="settings:toggle:schedule.monthly_review_enabled",
            ),
            InlineKeyboardButton("✏️ time", callback_data="settings:ask:schedule.monthly_review_time"),
        ],
        [InlineKeyboardButton("← Back", callback_data="settings:page:main")],
    ])


def settings_ai_keyboard(config) -> InlineKeyboardMarkup:
    p = config.ai.provider

    def _mark(v: str) -> str:
        return f"✓ {v}" if v == p else v

    model_label = config.ai.model if len(config.ai.model) <= 24 else config.ai.model[:22] + "…"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(_mark("anthropic"),   callback_data="settings:set:ai.provider:anthropic"),
            InlineKeyboardButton(_mark("ollama"),      callback_data="settings:set:ai.provider:ollama"),
            InlineKeyboardButton(_mark("claude_code"), callback_data="settings:set:ai.provider:claude_code"),
        ],
        [InlineKeyboardButton(
            f"Model: {model_label}  ✏️",
            callback_data="settings:ask:ai.model",
        )],
        [InlineKeyboardButton("← Back", callback_data="settings:page:main")],
    ])


def settings_language_keyboard(config) -> InlineKeyboardMarkup:
    locale = config.locale

    def _mark(v: str, label: str) -> str:
        return f"✓ {label}" if v == locale else label

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(_mark("uk", "🇺🇦 Українська"), callback_data="settings:set:locale:uk"),
            InlineKeyboardButton(_mark("en", "🇬🇧 English"),     callback_data="settings:set:locale:en"),
        ],
        [InlineKeyboardButton("← Back", callback_data="settings:page:main")],
    ])
