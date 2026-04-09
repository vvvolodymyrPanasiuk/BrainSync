"""Scheduled summary job handlers for Telegram bot."""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from pathlib import Path

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
    """Send weekly report: notes by topic, most active days, open tasks + PNG chart."""
    index = context.bot_data["index"]
    config = context.bot_data["config"]

    today = date.today()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    week_end = today.isoformat()

    weekly = [note for note in index.notes.values() if week_start <= note.date <= week_end]

    by_topic: dict[str, int] = {}
    for note in weekly:
        top = note.folder.split("/")[0]
        by_topic[top] = by_topic.get(top, 0) + 1

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

    caption = "\n".join(lines)
    chart = _build_weekly_chart(by_topic, by_day, week_start, week_end)
    await _send_to_user(context, caption, photo=chart)


async def monthly_summary_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send monthly report: total notes, top topics, growth trend + PNG chart."""
    index = context.bot_data["index"]

    today = date.today()
    month_prefix = today.strftime("%Y-%m")

    monthly = [note for note in index.notes.values() if note.date.startswith(month_prefix)]

    first_day = today.replace(day=1)
    prev_last = first_day - timedelta(days=1)
    prev_prefix = prev_last.strftime("%Y-%m")
    prev_monthly = [note for note in index.notes.values() if note.date.startswith(prev_prefix)]

    by_topic: dict[str, int] = {}
    for note in monthly:
        top = note.folder.split("/")[0]
        by_topic[top] = by_topic.get(top, 0) + 1

    prev_by_topic: dict[str, int] = {}
    for note in prev_monthly:
        top = note.folder.split("/")[0]
        prev_by_topic[top] = prev_by_topic.get(top, 0) + 1

    note_types: dict[str, int] = {}
    for note in monthly:
        nt = note.note_type.value if hasattr(note.note_type, "value") else str(note.note_type)
        note_types[nt] = note_types.get(nt, 0) + 1

    # Per-day activity for current month
    by_day: dict[str, int] = {}
    for note in monthly:
        by_day[note.date] = by_day.get(note.date, 0) + 1

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

    caption = "\n".join(lines)
    chart = _build_monthly_chart(by_topic, prev_by_topic, note_types, by_day, month_prefix, prev_prefix)
    await _send_to_user(context, caption, photo=chart)


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


async def stale_task_reminder_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remind about tasks that have been open longer than stale_task_days."""
    config = context.bot_data["config"]
    index = context.bot_data["index"]

    threshold = (date.today() - timedelta(days=config.schedule.stale_task_days)).isoformat()
    vault = Path(config.vault.path)
    pattern = re.compile(r"^- \[ \] (.+)$", re.MULTILINE)

    stale: list[dict] = []
    for path, note in index.notes.items():
        if note.note_type.value != "task":
            continue
        if note.date > threshold:   # created recently — not stale
            continue
        try:
            content = (vault / path).read_text(encoding="utf-8")
        except Exception:
            continue
        tasks = pattern.findall(content)
        if tasks:
            stale.append({"note": path, "date": note.date, "tasks": tasks})

    if not stale:
        return

    lines = [
        f"⏰ Stale tasks (open > {config.schedule.stale_task_days} days) — "
        f"{date.today().isoformat()}\n"
    ]
    for item in stale[:10]:
        lines.append(f"📋 {item['note']} ({item['date']})")
        for task in item["tasks"][:3]:
            lines.append(f"  - [ ] {task}")
        if len(item["tasks"]) > 3:
            lines.append(f"  … +{len(item['tasks']) - 3} more")
    if len(stale) > 10:
        lines.append(f"\n… and {len(stale) - 10} more note(s) with stale tasks")

    await _send_to_user(context, "\n".join(lines))


async def _send_to_user(context: ContextTypes.DEFAULT_TYPE, text: str, photo=None) -> None:
    """Send text message or photo with caption to the first allowed user."""
    config = context.bot_data["config"]
    if not config.telegram.allowed_user_ids:
        return
    user_id = config.telegram.allowed_user_ids[0]
    try:
        if photo is not None:
            photo.seek(0)
            await context.bot.send_photo(chat_id=user_id, photo=photo, caption=text)
        else:
            await context.bot.send_message(chat_id=user_id, text=text)
    except Exception as exc:
        logger.warning("Failed to send summary: %s", exc)
        # Fallback: send as plain text if photo failed
        if photo is not None:
            try:
                await context.bot.send_message(chat_id=user_id, text=text)
            except Exception:
                pass


def _build_weekly_chart(
    by_topic: dict,
    by_day: dict,
    week_start: str,
    week_end: str,
):
    """Build a 2-panel weekly summary chart. Returns BytesIO or None."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import io
        from datetime import date as _date, timedelta as _td
    except ImportError:
        return None

    try:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))
        fig.patch.set_facecolor("#1e1e2e")
        _apply_dark(fig)

        # Left: bar chart by topic
        if by_topic:
            topics = sorted(by_topic, key=by_topic.get)
            counts = [by_topic[t] for t in topics]
            bars = ax1.barh(topics, counts, color="#89b4fa")
            ax1.bar_label(bars, padding=3, color="#cdd6f4", fontsize=8)
        ax1.set_title("Notes by topic", color="#cdd6f4", fontsize=10)
        _style_ax(ax1)

        # Right: daily activity line for the 7 days of this week
        start = _date.fromisoformat(week_start)
        days = [(start + _td(days=i)).isoformat() for i in range(7)]
        day_labels = [(start + _td(days=i)).strftime("%a") for i in range(7)]
        counts7 = [by_day.get(d, 0) for d in days]
        ax2.fill_between(range(7), counts7, color="#a6e3a1", alpha=0.5)
        ax2.plot(range(7), counts7, color="#a6e3a1", marker="o", markersize=5)
        ax2.set_xticks(range(7))
        ax2.set_xticklabels(day_labels, color="#cdd6f4", fontsize=8)
        ax2.set_title(f"Daily activity ({week_start} – {week_end})", color="#cdd6f4", fontsize=10)
        _style_ax(ax2)

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", facecolor=fig.get_facecolor(), dpi=110)
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception as exc:
        logger.warning("_build_weekly_chart: %s", exc)
        return None


def _build_monthly_chart(
    by_topic: dict,
    prev_by_topic: dict,
    note_types: dict,
    by_day: dict,
    month_prefix: str,
    prev_prefix: str,
):
    """Build a 3-panel monthly summary chart. Returns BytesIO or None."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
        import io
        import calendar
        from datetime import date as _date
    except ImportError:
        return None

    try:
        fig, axes = plt.subplots(1, 3, figsize=(15, 4))
        fig.patch.set_facecolor("#1e1e2e")
        ax1, ax2, ax3 = axes
        _apply_dark(fig)

        # Left: current vs previous month by topic
        all_topics = sorted(set(list(by_topic.keys()) + list(prev_by_topic.keys())))
        if all_topics:
            x = np.arange(len(all_topics))
            w = 0.4
            curr_vals = [by_topic.get(t, 0) for t in all_topics]
            prev_vals = [prev_by_topic.get(t, 0) for t in all_topics]
            ax1.barh(x - w / 2, curr_vals, w, label=month_prefix, color="#89b4fa")
            ax1.barh(x + w / 2, prev_vals, w, label=prev_prefix, color="#585b70")
            ax1.set_yticks(x)
            ax1.set_yticklabels(all_topics, color="#cdd6f4", fontsize=7)
            ax1.legend(fontsize=7, labelcolor="#cdd6f4", facecolor="#313244", framealpha=0.5)
        ax1.set_title("This vs last month", color="#cdd6f4", fontsize=10)
        _style_ax(ax1)

        # Centre: note types pie
        if note_types:
            labels = list(note_types.keys())
            sizes = list(note_types.values())
            colors = ["#89b4fa", "#a6e3a1", "#fab387", "#f38ba8", "#cba6f7"][:len(labels)]
            ax2.pie(sizes, labels=labels, colors=colors, autopct="%1.0f%%",
                    textprops={"color": "#cdd6f4", "fontsize": 8})
        ax2.set_title("Note types", color="#cdd6f4", fontsize=10)
        ax2.set_facecolor("#1e1e2e")

        # Right: per-day activity for the month
        year, month = map(int, month_prefix.split("-"))
        days_in_month = calendar.monthrange(year, month)[1]
        day_dates = [f"{month_prefix}-{d:02d}" for d in range(1, days_in_month + 1)]
        day_counts = [by_day.get(d, 0) for d in day_dates]
        ax3.fill_between(range(days_in_month), day_counts, color="#cba6f7", alpha=0.5)
        ax3.plot(range(days_in_month), day_counts, color="#cba6f7", linewidth=1.5)
        tick_pos = [0, days_in_month // 4, days_in_month // 2, 3 * days_in_month // 4, days_in_month - 1]
        ax3.set_xticks(tick_pos)
        ax3.set_xticklabels([day_dates[i][8:] for i in tick_pos], color="#cdd6f4", fontsize=8)
        ax3.set_title(f"Daily activity — {month_prefix}", color="#cdd6f4", fontsize=10)
        _style_ax(ax3)

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", facecolor=fig.get_facecolor(), dpi=110)
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception as exc:
        logger.warning("_build_monthly_chart: %s", exc)
        return None


def _style_ax(ax) -> None:
    ax.set_facecolor("#1e1e2e")
    ax.tick_params(colors="#cdd6f4", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#313244")


def _apply_dark(fig) -> None:
    for ax in fig.axes:
        _style_ax(ax)
