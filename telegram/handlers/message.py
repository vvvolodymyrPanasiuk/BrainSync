"""Telegram plain-text message handler: AI semantic routing via ActionPlan."""
from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.error import RetryAfter
from telegram.ext import ContextTypes

from vault_writer.tools.create_note import detect_prefix, handle_create_note
from vault_writer.vault.writer import NoteType

logger = logging.getLogger(__name__)

_SPLIT_THRESHOLD = 3900    # chars near Telegram's 4096 limit → likely a split part
_BUFFER_TIMEOUT  = 5.0     # seconds to wait for more parts before processing
_MAX_BUFFER      = 200_000 # hard cap: flush immediately if exceeded
_BUF_KEY         = "_msg_buf"
_BUF_UPD_KEY     = "_msg_buf_upd"


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route plain-text Telegram message; accumulate split parts before processing."""
    from telegram.handlers.commands import auth_check
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return

    text = update.message.text or ""
    if not text.strip():
        return

    user_id = update.effective_user.id

    # Short message + no active buffer → skip buffering (zero extra latency)
    if len(text) < _SPLIT_THRESHOLD and not context.user_data.get(_BUF_KEY):
        await _process_message(update, context, text)
        return

    # Accumulate
    buf = context.user_data.setdefault(_BUF_KEY, [])
    buf.append(text)
    context.user_data[_BUF_UPD_KEY] = update

    # Cancel any pending flush for this user
    for job in context.job_queue.get_jobs_by_name(f"_flush_{user_id}"):
        job.schedule_removal()

    if sum(len(x) for x in buf) >= _MAX_BUFFER:
        merged = "\n".join(context.user_data.pop(_BUF_KEY))
        context.user_data.pop(_BUF_UPD_KEY, None)
        await _process_message(update, context, merged)
        return

    context.job_queue.run_once(
        _flush_job,
        _BUFFER_TIMEOUT,
        name=f"_flush_{user_id}",
        user_id=user_id,
        chat_id=update.effective_chat.id,
    )


async def _flush_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """PTB job: merge buffered message parts and process as one."""
    buf    = context.user_data.pop(_BUF_KEY, [])
    update = context.user_data.pop(_BUF_UPD_KEY, None)
    if not buf or update is None:
        return
    await _process_message(update, context, "\n".join(buf))


async def _process_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Core message handler (receives final merged text)."""
    config = context.bot_data["config"]

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )

    provider    = context.bot_data.get("provider")
    vector_store = context.bot_data.get("vector_store")
    index        = context.bot_data["index"]
    stats        = context.bot_data["stats"]

    # ── Active YouTube session: consume message as a question ─────────────────
    from telegram.handlers.youtube_chat import handle_question, has_active_session
    if has_active_session(context):
        consumed = await handle_question(update, context)
        if consumed:
            return

    # ── Bare YouTube URL → NotebookLM session ─────────────────────────────────
    if _is_youtube_url(text.strip()):
        from telegram.handlers.youtube_chat import start_session
        await start_session(update, context, text.strip())
        return

    # ── Bare non-YouTube URL → web clip ───────────────────────────────────────
    if _is_bare_url(text.strip()):
        from telegram.handlers.commands import _do_clip
        await _do_clip(update, context, text.strip())
        return

    # ── Pending settings text input ───────────────────────────────────────────
    from telegram.handlers.callbacks import handle_settings_text_input
    if await handle_settings_text_input(update, context):
        return

    # ── Pending inline actions (move / tags) ──────────────────────────────────
    if await _handle_pending_inline(update, context, text):
        return

    # ── Group topic context: inject folder hint into message ──────────────────
    text = _inject_topic_context(update, context, text)

    # ── Prefix detection (explicit type overrides AI routing) ─────────────────
    note_type, clean_text = detect_prefix(text, config.prefixes)
    if note_type is not None:
        # User explicitly typed a prefix (e.g., "задача: ...") — bypass router
        result = await _run_create_note(
            clean_text, note_type, None, config, index, stats, provider, vector_store
        )
        reply = _format_save_result(result, config)
        await _reply_with_retry(update, reply)
        if result.get("success") and config.git.enabled and config.git.auto_commit:
            _git_commit(result["file_path"], config)
        return

    # ── Explicit search prefixes (bypass AI router) ───────────────────────────
    # Order matters: ??? before ?? before ?
    if text.startswith("???"):
        query = text[3:].strip()
        if query:
            await _handle_forced_search(query, "combined", update, context, config, index, stats, provider, vector_store)
            return
    elif text.startswith("??"):
        query = text[2:].strip()
        if query:
            await _handle_forced_search(query, "web", update, context, config, index, stats, provider, vector_store)
            return
    elif text.startswith("?"):
        query = text[1:].strip()
        if query:
            await _handle_forced_search(query, "vault", update, context, config, index, stats, provider, vector_store)
            return

    # ── AI required ───────────────────────────────────────────────────────────
    if not context.bot_data.get("ai_ready", False):
        from telegram.i18n import t
        await _reply_with_retry(update, t("ai_not_ready"))
        return

    # ── Progress indicator (#6) ───────────────────────────────────────────────
    from telegram.i18n import t as _t
    progress_msg = None
    try:
        progress_msg = await update.message.reply_text(_t("progress_thinking"))
    except Exception:
        pass

    # ── Conversation context ──────────────────────────────────────────────────
    from vault_writer.ai.context_manager import (
        to_prompt_block, add_user_turn, add_assistant_turn,
        needs_compaction, detect_topic_shift, compact as compact_ctx,
    )
    history_block = to_prompt_block(context.user_data)

    # ── AI Semantic Router ────────────────────────────────────────────────────
    try:
        plan = await _route(text, provider, index, config.vault.language, history_block)
        # Search intents require an explicit ? prefix — redirect to chat otherwise
        from vault_writer.ai.router import Intent as _Intent
        _SEARCH_INTENTS = {
            _Intent.ANSWER_FROM_VAULT, _Intent.SEARCH_VAULT,
            _Intent.ANALYZE_VAULT, _Intent.SUMMARIZE_VAULT, _Intent.SEARCH_WEB,
        }
        if plan.intent in _SEARCH_INTENTS:
            plan.intent = _Intent.CHAT_ONLY
            plan.should_save = False
    except Exception as exc:
        logger.error("routing failed: %s", exc, exc_info=True)
        if progress_msg:
            try:
                await progress_msg.delete()
            except Exception:
                pass
        await _reply_with_retry(update, f"❌ AI error: `{exc}`")
        return

    # ── Executor ──────────────────────────────────────────────────────────────
    from vault_writer.tools.executor import execute
    reply, keyboard = await execute(
        plan=plan,
        message=text,
        update=update,
        context=context,
        config=config,
        index=index,
        stats=stats,
        provider=provider,
        vector_store=vector_store,
    )

    # Delete progress indicator before sending the real reply
    if progress_msg:
        try:
            await progress_msg.delete()
        except Exception:
            pass

    # ── Update conversation history ───────────────────────────────────────────
    full_folder = "/".join(p for p in [
        getattr(plan, "general_category", ""),
        getattr(plan, "target_folder", ""),
    ] if p)
    add_user_turn(context.user_data, text, intent=plan.intent.value, folder=full_folder)
    if reply:
        add_assistant_turn(context.user_data, reply, intent=plan.intent.value, folder=full_folder)

    # ── Topic shift detection → auto-compact ──────────────────────────────────
    compacted_notice = ""
    if detect_topic_shift(context.user_data, full_folder) or needs_compaction(context.user_data):
        loop2 = asyncio.get_running_loop()
        await loop2.run_in_executor(None, compact_ctx, context.user_data, provider)
        compacted_notice = "\n\n_💬 Контекст розмови стиснуто (нова тема або ліміт досягнуто)._"

    if reply:
        # Attach "💡 Save as note" only for vault-sourced synthesis answers (LLM-Wiki novelty gate):
        # - ANSWER_FROM_VAULT with actual results → AI synthesized from the user's own notes → worth saving
        # - CHAT_ONLY → generic AI knowledge, not personal insight → skip
        from vault_writer.ai.router import Intent as _Intent
        if plan.intent == _Intent.ANSWER_FROM_VAULT and keyboard is None and len(reply) > 120:
            context.user_data["last_insight"] = reply
            from telegram.keyboards import save_insight_keyboard
            keyboard = save_insight_keyboard()
        await _reply_with_retry(update, reply + compacted_notice, keyboard=keyboard)
    elif compacted_notice:
        await _reply_with_retry(update, compacted_notice.strip())

    # Git commit if a note was saved
    if plan.should_save and stats.last_note_path and config.git.enabled and config.git.auto_commit:
        _git_commit(stats.last_note_path, config)


# ── Routing ───────────────────────────────────────────────────────────────────

async def _route(text: str, provider, index, locale: str = "en", history_block: str = "") -> object:
    """Run AI router in executor. Raises on failure — caller handles the error."""
    from vault_writer.ai.router import route
    import functools
    loop = asyncio.get_running_loop()
    fn = functools.partial(route, text, provider, index, locale, history_block)
    return await loop.run_in_executor(None, fn)


# ── Legacy note creation (used by prefix path and /commands) ─────────────────

async def _run_create_note(
    text: str,
    note_type: NoteType | None,
    folder: str | None,
    config,
    index,
    stats,
    provider,
    vector_store=None,
) -> dict:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        handle_create_note,
        text, note_type, folder, config, index, stats, provider, vector_store,
    )


def _format_save_result(result: dict, config) -> str:
    if result.get("success"):
        from telegram.formatter import format_confirmation, format_similarity_notice
        reply = format_confirmation(result["file_path"])
        notices = result.get("similarity_notices", [])
        if notices:
            reply += "\n\n" + format_similarity_notice(notices)
        return reply
    return f"❌ Помилка: {result.get('error', 'невідома помилка')}"


# ── Retry helper ──────────────────────────────────────────────────────────────

async def _reply_with_retry(
    update: Update, text: str, max_attempts: int = 3, keyboard=None
) -> None:
    """Send reply, splitting into multiple messages if text exceeds 4000 chars."""
    from telegram.constants import ParseMode
    _MAX = 4000
    # Split on newlines where possible
    parts: list[str] = []
    while len(text) > _MAX:
        split_at = text.rfind("\n", 0, _MAX)
        if split_at <= 0:
            split_at = _MAX
        parts.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    parts.append(text)

    for i, part in enumerate(parts):
        kb = keyboard if i == len(parts) - 1 else None
        for attempt in range(max_attempts):
            try:
                await update.message.reply_text(
                    part,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=kb,
                )
                break
            except RetryAfter as exc:
                wait = exc.retry_after if attempt < max_attempts - 1 else None
                if wait is None:
                    await update.message.reply_text("⚠️ Telegram API тимчасово недоступний.")
                    return
                logger.warning("RetryAfter: waiting %ss (attempt %d)", wait, attempt + 1)
                await asyncio.sleep(wait)
            except Exception as exc:
                logger.error("reply_text failed: %s", exc)
                return


def _is_bare_url(text: str) -> bool:
    import re
    return bool(re.fullmatch(r'https?://\S+', text))


def _is_youtube_url(text: str) -> bool:
    import re
    return bool(re.match(r'https?://(www\.)?(youtube\.com/watch|youtu\.be/)', text))


def _inject_topic_context(update, context, text: str) -> str:
    """If message is from a forum topic thread, prepend the topic name as context hint.

    Stores topic_name → folder mapping in bot_data['topic_map'][chat_id][thread_id].
    The router then sees 'Topic: Trading — <message>' and routes to the right folder.
    """
    msg = update.message
    if not (getattr(msg, "is_topic_message", False) and msg.message_thread_id):
        return text

    chat_id   = str(msg.chat_id)
    thread_id = str(msg.message_thread_id)
    topic_map = context.bot_data.setdefault("topic_map", {})
    topic_name = topic_map.get(chat_id, {}).get(thread_id)

    if not topic_name:
        return text  # name not yet registered — still process normally

    return f"[Topic: {topic_name}] {text}"


async def _handle_pending_inline(update, context, text: str) -> bool:
    """Handle follow-up text for pending inline actions (move destination / tags).

    Returns True if the message was consumed.
    """
    config = context.bot_data["config"]
    vault  = config.vault.path

    # ── Pending move ──────────────────────────────────────────────────────────
    pending_move = context.user_data.pop("pending_move_path", None)
    if pending_move:
        dest_folder = text.strip().strip("/")
        from vault_writer.vault.writer import create_moc_if_missing, update_moc
        from vault_writer.vault.indexer import update_index
        from pathlib import Path

        src = Path(vault) / pending_move
        if not src.exists():
            await update.message.reply_text(f"❌ File not found: `{pending_move}`", parse_mode="Markdown")
            return True

        dest_dir = Path(vault) / dest_folder / "_data"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        src.rename(dest)
        new_rel = f"{dest_folder}/_data/{src.name}"

        index = context.bot_data["index"]
        old_note = index.notes.pop(pending_move, None)
        if old_note:
            old_note.file_path = new_rel
            old_note.folder = dest_folder
            index.notes[new_rel] = old_note

        vector_store = context.bot_data.get("vector_store")
        if vector_store:
            try:
                content = dest.read_text(encoding="utf-8")
                vector_store.delete_note(pending_move)
                vector_store.upsert_note(new_rel, content)
            except Exception:
                pass

        await update.message.reply_text(f"✅ Moved → `{new_rel}`", parse_mode="Markdown")
        return True

    # ── Pending tag addition ──────────────────────────────────────────────────
    pending_tags = context.user_data.pop("pending_tags_path", None)
    if pending_tags:
        new_tags = [t.strip().lstrip("#") for t in text.split() if t.strip()]
        if not new_tags:
            await update.message.reply_text("No tags provided.")
            return True

        from pathlib import Path
        import re
        full = Path(vault) / pending_tags
        if not full.exists():
            await update.message.reply_text(f"❌ File not found: `{pending_tags}`", parse_mode="Markdown")
            return True

        content = full.read_text(encoding="utf-8")
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                fm = content[3:end]
                tags_match = re.search(r'^tags:\n((?:  - .+\n)*)', fm, re.MULTILINE)
                if tags_match:
                    existing_block = tags_match.group(0)
                    addition = "".join(f"  - {t}\n" for t in new_tags)
                    new_fm = fm.replace(existing_block, existing_block.rstrip("\n") + "\n" + addition)
                    full.write_text(f"---{new_fm}---{content[end+3:]}", encoding="utf-8")

        await update.message.reply_text(
            f"🏷️ Tags added: {', '.join('#'+t for t in new_tags)}", parse_mode="Markdown"
        )
        return True

    return False


async def _handle_forced_search(
    query: str,
    mode: str,          # "vault" | "web"
    update,
    context,
    config,
    index,
    stats,
    provider,
    vector_store,
) -> None:
    """Execute a forced vault or web search without going through the AI router."""
    from telegram.i18n import t
    from vault_writer.ai.router import ActionPlan, Intent

    _progress_keys = {
        "vault": "vault_search_progress",
        "web": "web_search_progress",
        "combined": "combined_search_progress",
    }
    progress_key = _progress_keys.get(mode, "progress_thinking")

    progress_msg = None
    try:
        progress_msg = await update.message.reply_text(t(progress_key))
    except Exception:
        pass

    # "combined" mode: vault + web in one AI call — bypass ActionPlan/execute pipeline
    if mode == "combined":
        from vault_writer.tools.executor import _combined_vault_and_web
        reply = await _combined_vault_and_web(query, vector_store, provider, config)
        keyboard = None
    else:
        intent = Intent.ANSWER_FROM_VAULT if mode == "vault" else Intent.SEARCH_WEB
        plan = ActionPlan(
            intent=intent,
            confidence=1.0,
            should_save=False,
            needs_web=(mode == "web"),
            needs_clarification=False,
            note_type="note",
            general_category="",
            target_folder="",
            target_subfolder="",
            section="",
            topic=query[:60],
            tags=[],
            summary="",
            actions=[],
            sources=[],
            reason="explicit prefix",
            title="",
        )

        from vault_writer.tools.executor import execute
        reply, keyboard = await execute(
            plan=plan,
            message=query,
            update=update,
            context=context,
            config=config,
            index=index,
            stats=stats,
            provider=provider,
            vector_store=vector_store,
        )

    if progress_msg:
        try:
            await progress_msg.delete()
        except Exception:
            pass

    if reply:
        # Attach "Save as note" button to vault and combined answers
        if mode in ("vault", "combined") and keyboard is None:
            context.user_data["last_insight"] = reply
            from telegram.keyboards import save_insight_keyboard
            keyboard = save_insight_keyboard()
        await _reply_with_retry(update, reply, keyboard=keyboard)


def _git_commit(file_path: str, config) -> None:
    try:
        from git_sync.sync import commit_note
        commit_note(config.vault.path, file_path, config.git)
    except Exception as exc:
        logger.warning("git commit error: %s", exc)
