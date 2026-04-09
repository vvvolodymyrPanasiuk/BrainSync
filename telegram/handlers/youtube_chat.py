"""YouTube × NotebookLM session handler.

Flow:
  1. User sends a YouTube URL (bare URL auto-detected in message.py)
  2. Bot creates a NotebookLM notebook and adds the video as a source
  3. Each subsequent message is a question answered by NotebookLM chat API
  4. [💾 Save to vault] → preview summary → confirm → vault note created
  5. NotebookLM notebook deleted (cleanup)

Prerequisites:
  pip install "notebooklm-py[browser]"
  notebooklm login          # one-time Google auth via browser
"""
from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

_SESSION_KEY = "yt_session"


async def start_session(
    update: Update, context: ContextTypes.DEFAULT_TYPE, url: str
) -> None:
    """Create a NotebookLM notebook with the YouTube video and enter chat mode."""
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )
    await update.message.reply_text("⏳ Loading video into NotebookLM…")

    try:
        from notebooklm import NotebookLMClient
    except ImportError:
        await update.message.reply_text(
            "❌ `notebooklm-py` is not installed.\n\n"
            "Install it:\n"
            "```\npip install \"notebooklm-py[browser]\"\nnotebooklm login\n```",
            parse_mode="Markdown",
        )
        return

    try:
        async with await NotebookLMClient.from_storage() as client:
            nb = await client.notebooks.create(f"YT: {url[:80]}")
            await client.sources.add_youtube(nb.id, url)
            nb_id = nb.id

        context.user_data[_SESSION_KEY] = {
            "nb_id": nb_id,
            "url": url,
            "history": [],
        }

        from telegram.keyboards import youtube_chat_actions
        await update.message.reply_text(
            "✅ *Video loaded into NotebookLM.*\n\n"
            "Ask me anything about the video — I'll answer using NotebookLM.\n"
            "Press *Save to vault* when you're done.",
            parse_mode="Markdown",
            reply_markup=youtube_chat_actions(),
        )
    except Exception as exc:
        logger.error("youtube_chat: start_session: %s", exc)
        await update.message.reply_text(
            f"❌ NotebookLM error: `{exc}`\n\n"
            "Make sure you ran `notebooklm login` to authenticate your Google account.",
            parse_mode="Markdown",
        )


async def handle_question(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """Handle a user message within an active session.

    Returns True if the message was consumed by the YouTube session.
    """
    session = context.user_data.get(_SESSION_KEY)
    if not session:
        return False

    # User is sending edited note content to replace auto-generated summary
    if context.user_data.pop("yt_waiting_edit", False):
        session["edited_content"] = update.message.text or ""
        await confirm_save(update, context)
        return True

    text = update.message.text or ""
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )

    try:
        from notebooklm import NotebookLMClient
        async with await NotebookLMClient.from_storage() as client:
            result = await client.chat.ask(session["nb_id"], text)
            answer = result.answer
    except Exception as exc:
        logger.error("youtube_chat: ask: %s", exc)
        answer = f"❌ NotebookLM error: {exc}"

    session["history"].append({"q": text, "a": answer})

    from telegram.keyboards import youtube_chat_actions
    await update.message.reply_text(answer, reply_markup=youtube_chat_actions())
    return True


async def preview_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show a note preview and confirmation buttons before saving."""
    session = context.user_data.get(_SESSION_KEY)
    msg = update.callback_query.message if update.callback_query else update.message
    if not session:
        await msg.reply_text("No active YouTube session.")
        return

    summary = _build_note_content(session)
    preview = summary[:900] + ("…" if len(summary) > 900 else "")

    from telegram.keyboards import youtube_save_confirm
    await msg.reply_text(
        f"📝 *Note preview:*\n\n{preview}",
        parse_mode="Markdown",
        reply_markup=youtube_save_confirm(),
    )


async def confirm_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Save the session Q&A as a vault note and clean up the notebook."""
    session = context.user_data.pop(_SESSION_KEY, None)
    if not session:
        return

    content = session.get("edited_content") or _build_note_content(session)
    msg = update.callback_query.message if update.callback_query else update.message

    config       = context.bot_data["config"]
    index        = context.bot_data["index"]
    stats        = context.bot_data["stats"]
    provider     = context.bot_data.get("provider")
    vector_store = context.bot_data.get("vector_store")

    # Route for correct folder placement
    import asyncio
    loop = asyncio.get_running_loop()
    plan = None
    if provider is not None:
        try:
            from vault_writer.ai.router import route
            plan = await loop.run_in_executor(
                None, route,
                f"YouTube video notes: {session['url']}",
                provider, index, config.vault.language,
            )
        except Exception as exc:
            logger.warning("youtube_chat: route failed: %s", exc)

    if plan is None:
        from vault_writer.ai.router import ActionPlan, Intent
        plan = ActionPlan(
            intent=Intent.CREATE_NOTE, confidence=0.7, should_save=True,
            needs_web=False, needs_clarification=False, note_type="note",
            general_category="", target_folder="Media", target_subfolder="YouTube",
            section="", topic="YouTube notes", tags=[], summary="YouTube session",
            actions=["create_note"], sources=[session["url"]], reason="YouTube clip",
            title=f"YouTube: {session['url'][:60]}",
        )

    from vault_writer.tools.create_note import handle_create_note_from_plan
    result = await loop.run_in_executor(
        None, handle_create_note_from_plan,
        f"YouTube session: {session['url']}", plan,
        config, index, stats, provider, vector_store, content,
    )

    if result.get("success"):
        from telegram.formatter import format_confirmation
        await msg.reply_text(format_confirmation(result["file_path"]))
        if config.git.enabled and config.git.auto_commit:
            try:
                from git_sync.sync import commit_note
                commit_note(config.vault.path, result["file_path"], config.git)
            except Exception:
                pass
    else:
        await msg.reply_text(f"❌ Save failed: {result.get('error')}")

    # Cleanup: delete the temporary NotebookLM notebook
    try:
        from notebooklm import NotebookLMClient
        async with await NotebookLMClient.from_storage() as client:
            await client.notebooks.delete(session["nb_id"])
        logger.info("youtube_chat: deleted notebook %s", session["nb_id"])
    except Exception as exc:
        logger.debug("youtube_chat: cleanup failed: %s", exc)


async def end_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Discard the session without saving."""
    session = context.user_data.pop(_SESSION_KEY, None)
    if not session:
        return

    msg = update.callback_query.message if update.callback_query else update.message
    await msg.reply_text("Session ended — nothing saved.")

    try:
        from notebooklm import NotebookLMClient
        async with await NotebookLMClient.from_storage() as client:
            await client.notebooks.delete(session["nb_id"])
    except Exception:
        pass


def has_active_session(context: ContextTypes.DEFAULT_TYPE) -> bool:
    return bool(context.user_data.get(_SESSION_KEY))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_note_content(session: dict) -> str:
    lines = [f"## Source\n\n{session['url']}\n\n## Notes\n"]
    for item in session["history"]:
        lines.append(f"**Q:** {item['q']}\n\n{item['a']}\n")
    lines.append("\n## Links\n\n")
    return "\n".join(lines)
