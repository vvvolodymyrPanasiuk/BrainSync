"""Telegram slash command handlers."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from vault_writer.vault.writer import NoteType

logger = logging.getLogger(__name__)


def auth_check(update: Update, config) -> bool:
    """Return False and log warning if user is not in allowed_user_ids."""
    user_id = update.effective_user.id if update.effective_user else None
    if user_id not in config.telegram.allowed_user_ids:
        logger.warning("Unauthorized access attempt: user_id=%s", user_id)
        return False
    return True


async def cmd_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Використання: /note <текст>")
        return
    await _save_with_type(update, context, text, NoteType.NOTE)


async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Використання: /task <текст>")
        return
    await _save_with_type(update, context, text, NoteType.TASK)


async def cmd_idea(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Використання: /idea <текст>")
        return
    await _save_with_type(update, context, text, NoteType.IDEA)


async def cmd_journal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Використання: /journal <текст>")
        return
    await _save_with_type(update, context, text, NoteType.JOURNAL)


async def _save_with_type(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, note_type: NoteType) -> None:
    from telegram.constants import ChatAction
    from vault_writer.tools.create_note import handle_create_note
    from telegram.handlers.message import _run_create_note

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    config = context.bot_data["config"]
    index = context.bot_data["index"]
    stats = context.bot_data["stats"]
    provider = context.bot_data.get("provider")

    result = await _run_create_note(text, note_type, None, config, index, stats, provider)
    reply = _format_result(result, config)
    await update.message.reply_text(reply)

    # Git commit
    if result.get("success") and config.git.enabled and config.git.auto_commit:
        _git_commit(result["file_path"], config)


async def cmd_move(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Explicit note move: /move <тема нотатки> -> <папка призначення>"""
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return
    text = " ".join(context.args) if context.args else ""
    if not text or "->" not in text:
        await update.message.reply_text(
            "Використання: /move <тема нотатки> -> <папка призначення>\n"
            "Наприклад: /move лазанья -> Кулінарія"
        )
        return

    from telegram.constants import ChatAction
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    parts = text.split("->", 1)
    topic = parts[0].strip()
    dest_folder = parts[1].strip()

    # Build a minimal plan for the executor
    from vault_writer.ai.router import ActionPlan, Intent
    import asyncio
    plan = ActionPlan(
        intent=Intent.MOVE_NOTE,
        confidence=1.0,
        should_save=False,
        needs_web=False,
        needs_clarification=False,
        note_type="note",
        general_category="",
        target_folder=dest_folder,
        target_subfolder="",
        section="",
        topic=topic,
        tags=[],
        summary=topic,
        actions=["move_note"],
        sources=[],
        reason="explicit /move command",
        title=topic,
    )

    index = context.bot_data["index"]
    vector_store = context.bot_data.get("vector_store")

    loop = asyncio.get_running_loop()
    from vault_writer.tools.executor import _move_note
    reply = await _move_note(topic, plan, config, index, vector_store)
    await update.message.reply_text(reply, parse_mode="Markdown")


async def cmd_merge(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Merge the newly saved note with its detected duplicate."""
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return

    from telegram.i18n import t
    pending = context.user_data.get("pending_merge") if context.user_data else None
    if not pending:
        await update.message.reply_text(t("merge_no_pending"))
        return

    new_path: str = pending["new_path"]
    dup_path: str = pending["duplicate_path"]
    context.user_data.pop("pending_merge", None)

    from telegram.constants import ChatAction
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    from pathlib import Path
    vault = Path(config.vault.path)
    new_file = vault / new_path
    dup_file = vault / dup_path

    if not new_file.exists() or not dup_file.exists():
        await update.message.reply_text(t("merge_files_gone"))
        return

    try:
        new_content = new_file.read_text(encoding="utf-8")
        dup_content = dup_file.read_text(encoding="utf-8")
    except Exception as exc:
        logger.error("cmd_merge: read error: %s", exc)
        await update.message.reply_text(t("merge_failed", error=str(exc)))
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
            logger.warning("cmd_merge: AI merge failed: %s — concatenating", exc)
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
                logger.warning("cmd_merge: vector store update: %s", exc)

        index = context.bot_data["index"]
        index.notes.pop(new_path, None)

        await update.message.reply_text(
            t("merge_done", dest=dup_path, src=new_path), parse_mode="Markdown"
        )
    except Exception as exc:
        logger.error("cmd_merge: write error: %s", exc)
        await update.message.reply_text(t("merge_failed", error=str(exc)))


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return
    help_text = (
        "📋 BrainSync команди:\n\n"
        "/note <текст> — зберегти нотатку\n"
        "/task <текст> — зберегти задачу\n"
        "/idea <текст> — зберегти ідею\n"
        "/journal <текст> — запис у щоденник\n"
        "/search <запит> — пошук у vault\n"
        "/move <тема> -> <папка> — перемістити нотатку\n"
        "/merge — об'єднати нотатку з дублікатом\n"
        "/status — статус бота\n"
        "/help — ця довідка"
    )
    await update.message.reply_text(help_text)



async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return
    index = context.bot_data["index"]
    stats = context.bot_data["stats"]
    from telegram.formatter import format_status
    await update.message.reply_text(format_status(config, stats, index))


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("Використання: /search <запит>")
        return

    vector_store = context.bot_data.get("vector_store")
    if vector_store is not None:
        import asyncio
        from vault_writer.rag.engine import search_vault
        from telegram.formatter import format_semantic_search_results
        try:
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(
                None, search_vault, query, vector_store, config.embedding.top_k_results
            )
            await update.message.reply_text(format_semantic_search_results(results, query))
            return
        except Exception as exc:
            logger.warning("Semantic search failed, falling back to keyword: %s", exc)
            from telegram.formatter import format_search_degraded_notice
            await update.message.reply_text(format_search_degraded_notice())

    # Fallback: keyword search
    from vault_writer.tools.search_notes import handle_search_notes
    index = context.bot_data["index"]
    result = handle_search_notes(query=query, limit=10, folder=None, index=index, vault_path=config.vault.path)
    from telegram.formatter import format_search_results
    await update.message.reply_text(format_search_results(result.get("results", []), query))


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
