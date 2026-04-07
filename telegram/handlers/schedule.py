"""Scheduled summary job handlers for Telegram bot."""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta

from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def daily_summary_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send daily progress report: notes saved, topics covered, wikilinks added, pending tasks."""
    config = context.bot_data["config"]
    index = context.bot_data["index"]
    stats = context.bot_data.get("stats")

    today = date.today().isoformat()

    # Count today's notes from the vault index (survives restarts)
    todays_notes = [note for note in index.notes.values() if note.date == today]
    topics = sorted({note.folder.split("/")[0] for note in todays_notes})

    # Session-level wikilinks counter (resets with bot restart — best effort)
    wikilinks = getattr(stats, "wikilinks_added_today", 0) if stats else 0

    pending = get_pending_tasks(config.vault.path, index)

    lines = [f"📅 Daily summary — {today}\n"]
    lines.append(f"Notes saved: {len(todays_notes)}")
    if topics:
        lines.append(f"Topics: {', '.join(topics)}")
    if wikilinks > 0:
        lines.append(f"New wikilinks: {wikilinks}")
    if pending:
        lines.append(f"\n📋 Open tasks: {len(pending)}")
        for task in pending[:5]:
            lines.append(f"  - [ ] {task}")
        if len(pending) > 5:
            lines.append(f"  … and {len(pending) - 5} more")

    if len(todays_notes) == 0 and not pending:
        lines.append("No notes saved today.")

    # Reset daily counters for next day
    if stats:
        stats.notes_saved_today = 0
        stats.wikilinks_added_today = 0
        stats.topics_today = []

    await _send_to_user(context, "\n".join(lines))


async def weekly_summary_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send weekly report: notes by topic, most active days, open tasks."""
    index = context.bot_data["index"]
    config = context.bot_data["config"]

    today = date.today()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    week_end = today.isoformat()

    weekly = [note for note in index.notes.values() if week_start <= note.date <= week_end]

    # Group by top-level folder
    by_topic: dict[str, int] = {}
    for note in weekly:
        top = note.folder.split("/")[0]
        by_topic[top] = by_topic.get(top, 0) + 1

    # Notes per day
    by_day: dict[str, int] = {}
    for note in weekly:
        by_day[note.date] = by_day.get(note.date, 0) + 1

    pending = get_pending_tasks(config.vault.path, index)

    lines = [f"📊 Weekly review — {week_start} → {week_end}\n"]
    lines.append(f"Total notes: {len(weekly)}")

    if by_topic:
        lines.append("\nBy topic:")
        for topic, count in sorted(by_topic.items(), key=lambda x: -x[1]):
            lines.append(f"  {topic}: {count}")

    if by_day:
        most_active = max(by_day, key=by_day.get)
        lines.append(f"\nMost active day: {most_active} ({by_day[most_active]} notes)")

    if pending:
        lines.append(f"\n📋 Open tasks: {len(pending)}")
        for task in pending[:8]:
            lines.append(f"  - [ ] {task}")
        if len(pending) > 8:
            lines.append(f"  … and {len(pending) - 8} more")

    await _send_to_user(context, "\n".join(lines))


async def monthly_summary_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send monthly report: total notes, top topics, growth trend."""
    index = context.bot_data["index"]

    today = date.today()
    month_prefix = today.strftime("%Y-%m")

    # Current month
    monthly = [note for note in index.notes.values() if note.date.startswith(month_prefix)]

    # Previous month for comparison
    first_day = today.replace(day=1)
    prev_last = first_day - timedelta(days=1)
    prev_prefix = prev_last.strftime("%Y-%m")
    prev_monthly = [note for note in index.notes.values() if note.date.startswith(prev_prefix)]

    by_topic: dict[str, int] = {}
    for note in monthly:
        top = note.folder.split("/")[0]
        by_topic[top] = by_topic.get(top, 0) + 1

    note_types: dict[str, int] = {}
    for note in monthly:
        nt = note.note_type.value if hasattr(note.note_type, "value") else str(note.note_type)
        note_types[nt] = note_types.get(nt, 0) + 1

    diff = len(monthly) - len(prev_monthly)
    diff_str = f"+{diff}" if diff >= 0 else str(diff)

    lines = [f"📈 Monthly review — {month_prefix}\n"]
    lines.append(f"Notes this month: {len(monthly)} ({diff_str} vs last month)")
    lines.append(f"Total in vault: {index.total_notes}")

    if by_topic:
        lines.append("\nTop topics:")
        for topic, count in sorted(by_topic.items(), key=lambda x: -x[1])[:8]:
            lines.append(f"  {topic}: {count}")

    if note_types:
        lines.append("\nBy type:")
        for nt, count in sorted(note_types.items(), key=lambda x: -x[1]):
            lines.append(f"  {nt}: {count}")

    await _send_to_user(context, "\n".join(lines))


def get_pending_tasks(vault_path: str, index) -> list[str]:
    """Scan task-type notes for pending Obsidian Tasks format items."""
    from pathlib import Path
    pending: list[str] = []
    pattern = re.compile(r"^- \[ \] (.+)$", re.MULTILINE)

    for path, note in index.notes.items():
        if note.note_type.value != "task":
            continue
        try:
            full_path = Path(vault_path) / path
            content = full_path.read_text(encoding="utf-8")
            for match in pattern.finditer(content):
                pending.append(match.group(1))
        except Exception:
            continue
    return pending


async def _send_to_user(context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    config = context.bot_data["config"]
    if not config.telegram.allowed_user_ids:
        return
    user_id = config.telegram.allowed_user_ids[0]
    try:
        await context.bot.send_message(chat_id=user_id, text=text)
    except Exception as exc:
        logger.warning("Failed to send summary: %s", exc)
