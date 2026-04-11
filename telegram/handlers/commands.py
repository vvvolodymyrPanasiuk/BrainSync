"""Telegram slash command handlers."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


def auth_check(update: Update, config) -> bool:
    """Return False and log warning if user is not in allowed_user_ids."""
    user_id = update.effective_user.id if update.effective_user else None
    if user_id not in config.telegram.allowed_user_ids:
        logger.warning("Unauthorized access attempt: user_id=%s", user_id)
        return False
    return True



async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all notes and open tasks created today."""
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return

    from datetime import date
    from telegram.handlers.schedule import get_pending_tasks

    index = context.bot_data["index"]
    today = date.today().isoformat()
    todays = [n for n in index.notes.values() if n.date == today]

    lines = [f"📅 Today — {today}\n"]
    if todays:
        lines.append(f"Notes saved: {len(todays)}")
        for note in sorted(todays, key=lambda n: n.note_number)[:10]:
            lines.append(f"  · {note.title}  ({note.folder.split('/')[0]})")
        if len(todays) > 10:
            lines.append(f"  … and {len(todays)-10} more")
    else:
        lines.append("No notes yet today.")

    pending = get_pending_tasks(config.vault.path, index)
    if pending:
        lines.append(f"\n📋 Open tasks: {len(pending)}")
        for task in pending[:5]:
            lines.append(f"  - [ ] {task}")
        if len(pending) > 5:
            lines.append(f"  … and {len(pending)-5} more")

    await update.message.reply_text("\n".join(lines))


async def cmd_reload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reload config.yaml without restarting the bot."""
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return
    try:
        from config.loader import load_config
        new_config = load_config(config.config_path)
        context.bot_data["config"] = new_config
        await update.message.reply_text("✅ Config reloaded.")
    except Exception as exc:
        logger.error("cmd_reload: %s", exc)
        await update.message.reply_text(f"❌ Reload failed: `{exc}`", parse_mode="Markdown")




async def cmd_clip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clip a URL: fetch page, summarise with AI, save as note."""
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return
    url = " ".join(context.args).strip() if context.args else ""
    if not url or not url.startswith("http"):
        await update.message.reply_text("Usage: /clip <url>")
        return
    await _do_clip(update, context, url)


async def _do_clip(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str) -> None:
    """Shared logic for /clip command and auto-detected URLs in messages."""
    from telegram.constants import ChatAction
    from telegram.i18n import t
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    await update.message.reply_text(t("clip_fetching"))

    config = context.bot_data["config"]
    index = context.bot_data["index"]
    stats = context.bot_data["stats"]
    provider = context.bot_data.get("provider")
    vector_store = context.bot_data.get("vector_store")

    from vault_writer.tools.web_clip import fetch_url
    try:
        page_title, page_text = fetch_url(url)
    except Exception as exc:
        logger.warning("cmd_clip: fetch failed for %s: %s", url, exc)
        from telegram.formatter import format_clip_error
        await update.message.reply_text(format_clip_error(str(exc)))
        return

    # Build a note from the clipped content
    if provider is not None:
        import asyncio
        from telegram.i18n import t as _t
        await update.message.reply_text(_t("clip_summarising"))
        loop = asyncio.get_running_loop()
        try:
            summary = await loop.run_in_executor(
                None, provider.complete,
                f"Summarise the following web page into a well-structured Obsidian note body. "
                f"Use sections: Description, Key Points, Conclusions, Links. "
                f"Cite the source URL at the end. Return only the markdown body.\n\n"
                f"Title: {page_title}\nURL: {url}\n\nContent:\n{page_text}",
            )
            content_override = summary
        except Exception as exc:
            logger.warning("cmd_clip: AI summarise failed: %s — using raw text", exc)
            content_override = f"## Description\n\n{page_text}\n\n## Links\n\n- {url}\n"
    else:
        content_override = f"## Description\n\n{page_text}\n\n## Links\n\n- {url}\n"

    # Route with AI to determine folder, then save
    if context.bot_data.get("ai_ready") and provider is not None:
        import asyncio
        from vault_writer.ai.router import route
        loop = asyncio.get_running_loop()
        try:
            plan = await loop.run_in_executor(
                None, route, f"Web article: {page_title}", provider, index, config.vault.language
            )
        except Exception:
            plan = _minimal_plan(page_title)
    else:
        plan = _minimal_plan(page_title)

    plan.title = page_title

    from vault_writer.tools.create_note import handle_create_note_from_plan
    import asyncio
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, handle_create_note_from_plan,
        f"Web clip: {page_title}", plan, config, index, stats, provider, vector_store,
        content_override,
    )

    if result.get("success"):
        from telegram.formatter import format_clip_saved
        reply = format_clip_saved(result["file_path"], url)
    else:
        from telegram.formatter import format_clip_error
        reply = format_clip_error(result.get("error", "unknown error"))

    await update.message.reply_text(reply, parse_mode="Markdown")

    if result.get("success") and config.git.enabled and config.git.auto_commit:
        _git_commit(result["file_path"], config)


def _minimal_plan(title: str):
    """Build a minimal CREATE_NOTE ActionPlan used when AI router is unavailable."""
    from vault_writer.ai.router import ActionPlan, Intent
    return ActionPlan(
        intent=Intent.CREATE_NOTE,
        confidence=0.5,
        should_save=True,
        needs_web=False,
        needs_clarification=False,
        note_type="note",
        general_category="",
        target_folder="General",
        target_subfolder="",
        section="",
        topic=title[:60],
        tags=[],
        summary=title[:100],
        actions=["create_note"],
        sources=[],
        reason="web clip",
        title=title[:60],
    )


async def cmd_merge(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show merge confirmation dialog before actually merging."""
    config = context.bot_data["config"]
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if msg is None:
        return

    # auth check — use effective_user from update
    user_id = update.effective_user.id if update.effective_user else None
    if user_id not in config.telegram.allowed_user_ids:
        return

    from telegram.i18n import t
    pending = context.user_data.get("pending_merge") if context.user_data else None
    if not pending:
        await msg.reply_text(t("merge_no_pending"))
        return

    new_path: str = pending["new_path"]
    dup_path: str = pending["duplicate_path"]

    from telegram.keyboards import merge_confirm_keyboard
    await msg.reply_text(
        t("merge_confirm", new=new_path, dup=dup_path),
        parse_mode="Markdown",
        reply_markup=merge_confirm_keyboard(),
    )


async def _do_merge(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Perform the actual merge after confirmation (called from callback handler)."""
    query = update.callback_query
    config = context.bot_data["config"]

    from telegram.i18n import t
    pending = context.user_data.get("pending_merge") if context.user_data else None
    if not pending:
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(t("merge_no_pending"))
        return

    new_path: str = pending["new_path"]
    dup_path: str = pending["duplicate_path"]
    context.user_data.pop("pending_merge", None)

    await query.edit_message_reply_markup(reply_markup=None)

    from telegram.constants import ChatAction
    await context.bot.send_chat_action(
        chat_id=query.message.chat_id, action=ChatAction.TYPING
    )

    from pathlib import Path
    vault = Path(config.vault.path)
    new_file = vault / new_path
    dup_file = vault / dup_path

    if not new_file.exists() or not dup_file.exists():
        await query.message.reply_text(t("merge_files_gone"))
        return

    try:
        new_content = new_file.read_text(encoding="utf-8")
        dup_content = dup_file.read_text(encoding="utf-8")
    except Exception as exc:
        logger.error("_do_merge: read error: %s", exc)
        await query.message.reply_text(t("merge_failed", error=str(exc)))
        return

    provider = context.bot_data.get("provider")
    if provider is not None:
        import asyncio
        loop = asyncio.get_running_loop()
        try:
            merged = await loop.run_in_executor(
                None, provider.complete,
                "Merge these two similar notes into one comprehensive note. "
                "Keep the frontmatter from NOTE 1 (existing). "
                "Combine bodies, deduplicate content, preserve all unique information. "
                "Return only the complete merged markdown:\n\n"
                f"NOTE 1 (existing):\n{dup_content}\n\nNOTE 2 (new):\n{new_content}",
            )
        except Exception as exc:
            logger.warning("_do_merge: AI failed: %s — concatenating", exc)
            merged = dup_content.rstrip() + "\n\n---\n\n" + new_content
    else:
        merged = dup_content.rstrip() + "\n\n---\n\n" + new_content

    try:
        dup_file.write_text(merged, encoding="utf-8")
        new_file.unlink()

        vector_store = context.bot_data.get("vector_store")
        if vector_store is not None:
            try:
                vector_store.upsert_note(dup_path, merged)
                vector_store.delete_note(new_path)
            except Exception as exc:
                logger.warning("_do_merge: vector store update: %s", exc)

        index = context.bot_data["index"]
        index.notes.pop(new_path, None)

        await query.message.reply_text(
            t("merge_done", dest=dup_path, src=new_path), parse_mode="Markdown"
        )
    except Exception as exc:
        logger.error("_do_merge: write error: %s", exc)
        await query.message.reply_text(t("merge_failed", error=str(exc)))


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show interactive settings menu."""
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return
    from telegram.keyboards import settings_main_keyboard
    from telegram.i18n import t
    await update.message.reply_text(
        t("settings_header"),
        parse_mode="Markdown",
        reply_markup=settings_main_keyboard(),
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show detailed vault statistics, optionally with a chart."""
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return

    index = context.bot_data["index"]
    from telegram.i18n import t
    from collections import Counter
    from datetime import date, timedelta

    notes = list(index.notes.values())
    total = len(notes)

    # Per-folder counts
    folder_counts: Counter = Counter(n.folder.split("/")[0] for n in notes)
    top_folders = folder_counts.most_common(10)

    # Note types
    type_counts: Counter = Counter(n.note_type.value if hasattr(n.note_type, "value") else str(n.note_type) for n in notes)

    # Activity last 30 days
    today = date.today()
    last30 = Counter()
    for n in notes:
        try:
            d = date.fromisoformat(n.date)
            if (today - d).days <= 30:
                last30[n.date] += 1
        except Exception:
            pass

    lines = [t("stats_header"), f"\n*Total notes:* {total}\n"]

    if top_folders:
        lines.append("*By folder:*")
        for folder, count in top_folders:
            bar = "█" * min(count, 20)
            lines.append(f"  `{folder:<20}` {bar} {count}")

    if type_counts:
        lines.append("\n*By type:*")
        for tp, count in type_counts.most_common():
            lines.append(f"  {tp}: {count}")

    if last30:
        active_days = len(last30)
        peak_day = max(last30, key=last30.get)
        peak_count = last30[peak_day]
        lines.append(f"\n*Last 30 days:* {sum(last30.values())} notes across {active_days} days")
        lines.append(f"*Best day:* {peak_day} ({peak_count} notes)")

    gamification_path = None
    try:
        from pathlib import Path
        import json
        gf = Path(config.vault.path) / ".brainsync" / "gamification.json"
        if gf.exists():
            g = json.loads(gf.read_text(encoding="utf-8"))
            level = g.get("level_name", "")
            xp = g.get("total_xp", 0)
            streak = g.get("streak_days", 0)
            lines.append(f"\n*Level:* {level} ({xp} XP)")
            lines.append(f"*Current streak:* {streak} days 🔥")
    except Exception:
        pass

    # Try to send a chart
    chart_sent = False
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import io

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
        fig.patch.set_facecolor("#1e1e2e")

        # Bar chart: top folders
        if top_folders:
            labels, values = zip(*top_folders[:8])
            ax1.barh(labels, values, color="#89b4fa")
            ax1.set_facecolor("#1e1e2e")
            ax1.tick_params(colors="#cdd6f4")
            ax1.set_title("Notes by folder", color="#cdd6f4")
            for spine in ax1.spines.values():
                spine.set_edgecolor("#313244")

        # Line chart: activity last 30 days
        if last30:
            days = [(today - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
            counts = [last30.get(d, 0) for d in days]
            ax2.fill_between(range(30), counts, color="#a6e3a1", alpha=0.6)
            ax2.plot(range(30), counts, color="#a6e3a1")
            ax2.set_facecolor("#1e1e2e")
            ax2.tick_params(colors="#cdd6f4")
            ax2.set_title("Activity (last 30 days)", color="#cdd6f4")
            ax2.set_xticks([0, 9, 19, 29])
            ax2.set_xticklabels([days[0][5:], days[9][5:], days[19][5:], days[29][5:]])
            for spine in ax2.spines.values():
                spine.set_edgecolor("#313244")

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        await update.message.reply_photo(buf, caption="\n".join(lines), parse_mode="Markdown")
        chart_sent = True
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("cmd_stats: chart failed: %s", exc)

    if not chart_sent:
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")




async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return
    from telegram.i18n import t
    from telegram.constants import ParseMode
    await update.message.reply_text(t("help_text"), parse_mode=ParseMode.MARKDOWN)



async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return
    index = context.bot_data["index"]
    stats = context.bot_data["stats"]
    from telegram.formatter import format_status
    await update.message.reply_text(format_status(config, stats, index))



async def cmd_reindex(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return
    vector_store = context.bot_data.get("vector_store")
    if vector_store is None:
        await update.message.reply_text("❌ Embedding backend недоступний. Перевірте налаштування.")
        return

    from telegram.formatter import format_reindex_done, format_reindex_start
    await update.message.reply_text(format_reindex_start())

    import asyncio
    loop = asyncio.get_running_loop()
    try:
        count = await loop.run_in_executor(
            None, vector_store.build_from_vault, config.vault.path, config.embedding
        )
        await update.message.reply_text(format_reindex_done(count))
    except Exception as exc:
        logger.error("cmd_reindex error: %s", exc)
        await update.message.reply_text("❌ Embedding backend недоступний. Перевірте налаштування.")


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
