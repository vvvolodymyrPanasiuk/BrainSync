"""Scheduled summary job handlers for Telegram bot."""
from __future__ import annotations

import logging
import re
from calendar import monthrange
from datetime import date, timedelta

from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def daily_summary_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send daily summary: today's notes + pending tasks."""
    config = context.bot_data["config"]
    index = context.bot_data["index"]

    today = date.today().isoformat()
    todays_notes = [
        note.file_path for note in index.notes.values()
        if note.date == today
    ]
    pending = get_pending_tasks(config.vault.path, index)

    lines = [f"📅 Щоденний підсумок — {today}\n"]
    lines.append(f"Нотаток сьогодні: {len(todays_notes)}")
    for path in todays_notes[:10]:
        lines.append(f"  • {path}")
    if pending:
        lines.append(f"\n📋 Відкритих задач: {len(pending)}")
        for task in pending[:5]:
            lines.append(f"  - [ ] {task}")

    await _send_to_user(context, "\n".join(lines))


async def weekly_summary_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send weekly summary: notes added this week grouped by topic."""
    config = context.bot_data["config"]
    index = context.bot_data["index"]

    today = date.today()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    week_end = today.isoformat()

    weekly = [
        note for note in index.notes.values()
        if week_start <= note.date <= week_end
    ]

    by_topic: dict[str, int] = {}
    for note in weekly:
        by_topic[note.folder] = by_topic.get(note.folder, 0) + 1

    lines = [f"📊 Тижневий огляд — {week_start} – {week_end}\n"]
    lines.append(f"Всього нотаток: {len(weekly)}")
    for topic, count in sorted(by_topic.items(), key=lambda x: -x[1]):
        lines.append(f"  {topic}: {count}")

    await _send_to_user(context, "\n".join(lines))


async def monthly_summary_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send monthly summary: notes added this month from frontmatter date field."""
    config = context.bot_data["config"]
    index = context.bot_data["index"]

    today = date.today()
    month_prefix = today.strftime("%Y-%m")

    monthly = [
        note for note in index.notes.values()
        if note.date.startswith(month_prefix)
    ]

    new_topics = set(note.folder for note in monthly)

    lines = [f"📈 Місячний огляд — {month_prefix}\n"]
    lines.append(f"Нотаток цього місяця: {len(monthly)}")
    lines.append(f"Нових тем: {len(new_topics)}")
    for topic in sorted(new_topics):
        lines.append(f"  • {topic}")

    await _send_to_user(context, "\n".join(lines))


def get_pending_tasks(vault_path: str, index) -> list[str]:
    """Scan task-type notes for pending Obsidian Tasks format items. Zero AI calls."""
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
