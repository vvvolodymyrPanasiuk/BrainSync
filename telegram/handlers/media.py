"""Media message handler: voice, photo, PDF, plain text files."""
from __future__ import annotations

import asyncio
import functools
import logging
import os
import tempfile
from enum import Enum

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from vault_writer.tools.create_note import detect_prefix, handle_create_note

logger = logging.getLogger(__name__)

# Set to True by _ensure_infrastructure_ready() in main.py after model download
_READY = False


class MediaType(str, Enum):
    VOICE = "voice"
    PHOTO = "photo"
    PDF = "pdf"
    TEXT_FILE = "text_file"
    UNSUPPORTED = "unsupported"


async def handle_media_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Auth check → typing indicator → detect MediaType → route to handler."""
    from telegram.handlers.commands import auth_check
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return

    msg = update.message
    if msg is None:
        return

    if msg.voice:
        media_type = MediaType.VOICE
    elif msg.photo:
        media_type = MediaType.PHOTO
    elif msg.document:
        mime = msg.document.mime_type or ""
        if mime == "application/pdf":
            media_type = MediaType.PDF
        elif mime in ("text/plain", "text/markdown"):
            media_type = MediaType.TEXT_FILE
        else:
            media_type = MediaType.UNSUPPORTED
    else:
        media_type = MediaType.UNSUPPORTED

    logger.info("media message received: type=%s", media_type.value)

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    if media_type == MediaType.VOICE:
        await _handle_voice(update, context)
    elif media_type == MediaType.PHOTO:
        await _handle_photo(update, context)
    else:
        await _handle_document(update, context, media_type)


async def _handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _READY
    config = context.bot_data["config"]

    if not _READY:
        await update.message.reply_text("⏳ Модель транскрипції завантажується… Спробуйте пізніше.")
        return

    voice = update.message.voice
    if voice.duration > config.media.max_voice_duration_seconds:
        from telegram.formatter import format_voice_duration_error
        await update.message.reply_text(format_voice_duration_error(config.media.max_voice_duration_seconds))
        return

    tmp_path = None
    try:
        voice_file = await voice.get_file()
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".ogg")
        os.close(tmp_fd)
        await voice_file.download_to_drive(tmp_path)

        transcriber = context.bot_data.get("transcriber")
        result = await asyncio.get_running_loop().run_in_executor(
            None, transcriber.transcribe, tmp_path
        )
        logger.info(
            "transcription complete: duration=%.1fs lang=%s",
            result.duration_seconds,
            result.language,
        )

        caption = update.message.caption or ""
        text = f"{caption} {result.text}".strip() if caption else result.text

        index = context.bot_data["index"]
        stats = context.bot_data["stats"]
        provider = context.bot_data.get("provider")
        vector_store = context.bot_data.get("vector_store")

        # Check explicit prefix first; otherwise route via AI semantic router
        note_type, clean_text = detect_prefix(text, config.prefixes)
        if note_type is not None:
            create_result = await _run_create_note(
                clean_text, note_type, None, config, index, stats, provider, vector_store
            )
            if create_result.get("success"):
                from telegram.formatter import format_confirmation, format_similarity_notice
                reply = format_confirmation(create_result["file_path"])
                notices = create_result.get("similarity_notices", [])
                if notices:
                    reply += "\n\n" + format_similarity_notice(notices)
                if config.git.enabled and config.git.auto_commit:
                    _git_commit(create_result["file_path"], config)
            else:
                reply = f"❌ Помилка: {create_result.get('error', 'невідома помилка')}"
        else:
            reply = await _route_and_execute(
                text, update, context, config, index, stats, provider, vector_store
            )

        await update.message.reply_text(reply)

    except Exception as exc:
        logger.error("_handle_voice error: %s", exc)
        from telegram.formatter import format_media_processing_error
        await update.message.reply_text(format_media_processing_error())
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


async def _handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data["config"]
    provider = context.bot_data.get("provider")

    try:
        photo = update.message.photo[-1]
        photo_file = await photo.get_file()
        image_bytes = bytes(await photo_file.download_as_bytearray())
        logger.info("photo downloaded: size=%d bytes provider=%s", len(image_bytes), config.ai.provider)

        description = ""
        try:
            if provider is not None:
                description = await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: provider.complete_with_image(
                        "Опиши що зображено на фото детально.",
                        image_bytes,
                        "image/jpeg",
                    ),
                )
                logger.info("photo described by provider=%s", config.ai.provider)
        except NotImplementedError:
            await update.message.reply_text(
                "⚠️ Модель не підтримує зображення. Збережено лише текст."
            )

        caption = update.message.caption or ""
        text = f"{caption} {description}".strip() if caption else description
        if not text:
            text = caption or "photo"

        index = context.bot_data["index"]
        stats = context.bot_data["stats"]
        vector_store = context.bot_data.get("vector_store")

        note_type, clean_text = detect_prefix(text, config.prefixes)
        if note_type is not None:
            create_result = await _run_create_note(
                clean_text or text, note_type, None, config, index, stats, provider, vector_store
            )
            if create_result.get("success"):
                from telegram.formatter import format_confirmation, format_similarity_notice
                reply = format_confirmation(create_result["file_path"])
                notices = create_result.get("similarity_notices", [])
                if notices:
                    reply += "\n\n" + format_similarity_notice(notices)
                if config.git.enabled and config.git.auto_commit:
                    _git_commit(create_result["file_path"], config)
            else:
                reply = f"❌ Помилка: {create_result.get('error', 'невідома помилка')}"
        else:
            reply = await _route_and_execute(
                text, update, context, config, index, stats, provider, vector_store
            )

        await update.message.reply_text(reply)

    except Exception as exc:
        logger.error("_handle_photo error: %s", exc)
        from telegram.formatter import format_media_processing_error
        await update.message.reply_text(format_media_processing_error())


async def _handle_document(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    media_type: MediaType,
) -> None:
    config = context.bot_data["config"]

    if media_type == MediaType.UNSUPPORTED:
        from telegram.formatter import format_unsupported_file_type
        await update.message.reply_text(format_unsupported_file_type())
        return

    doc = update.message.document
    file_size_mb = (doc.file_size or 0) / (1024 * 1024)
    if file_size_mb > config.media.max_file_size_mb:
        from telegram.formatter import format_file_too_large
        await update.message.reply_text(format_file_too_large(config.media.max_file_size_mb))
        return

    tmp_path = None
    try:
        doc_file = await doc.get_file()
        file_bytes = bytes(await doc_file.download_as_bytearray())
        logger.info(
            "document downloaded: type=%s size_mb=%.2f filename=%s",
            media_type.value,
            file_size_mb,
            doc.file_name or "",
        )

        index = context.bot_data["index"]
        stats = context.bot_data["stats"]
        provider = context.bot_data.get("provider")
        vector_store = context.bot_data.get("vector_store")
        caption = update.message.caption or ""

        if media_type == MediaType.PDF:
            from vault_writer.media.pdf_extractor import extract
            extracted = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: extract(
                    file_bytes,
                    config.media.pdf_max_pages,
                    config.media.pdf_ai_context_chars,
                    source_filename=doc.file_name or "",
                ),
            )
            logger.info(
                "pdf extracted: pages=%d truncated=%s",
                extracted.pages_extracted,
                extracted.truncated,
            )

            if not extracted.full_text.strip():
                from telegram.formatter import format_pdf_scanned_error
                await update.message.reply_text(format_pdf_scanned_error())
                return

            text = f"{caption} {extracted.ai_context}".strip() if caption else extracted.ai_context
            note_type, clean_text = detect_prefix(text, config.prefixes)

            if note_type is not None:
                # Explicit prefix — bypass router
                create_result = await _run_create_note(
                    clean_text, note_type, None, config, index, stats, provider, vector_store,
                    content_override=extracted.full_text,
                )
                if create_result.get("success"):
                    from telegram.formatter import format_confirmation, format_similarity_notice
                    reply = format_confirmation(create_result["file_path"])
                    if extracted.truncated:
                        from telegram.formatter import format_pdf_truncated_notice
                        reply += f"\n{format_pdf_truncated_notice(extracted.pages_extracted)}"
                    notices = create_result.get("similarity_notices", [])
                    if notices:
                        reply += "\n\n" + format_similarity_notice(notices)
                    if config.git.enabled and config.git.auto_commit:
                        _git_commit(create_result["file_path"], config)
                else:
                    reply = f"❌ Помилка: {create_result.get('error', 'невідома помилка')}"
            else:
                # Route via AI router; inject full_text as content_override
                reply = await _route_and_execute(
                    text, update, context, config, index, stats, provider, vector_store,
                    content_override=extracted.full_text,
                )
                if extracted.truncated:
                    from telegram.formatter import format_pdf_truncated_notice
                    reply += f"\n{format_pdf_truncated_notice(extracted.pages_extracted)}"

        else:  # MediaType.TEXT_FILE
            content = file_bytes.decode("utf-8", errors="replace")
            text = f"{caption} {content}".strip() if caption else content
            note_type, clean_text = detect_prefix(text, config.prefixes)

            if note_type is not None:
                create_result = await _run_create_note(
                    clean_text, note_type, None, config, index, stats, provider, vector_store
                )
                if create_result.get("success"):
                    from telegram.formatter import format_confirmation, format_similarity_notice
                    reply = format_confirmation(create_result["file_path"])
                    notices = create_result.get("similarity_notices", [])
                    if notices:
                        reply += "\n\n" + format_similarity_notice(notices)
                    if config.git.enabled and config.git.auto_commit:
                        _git_commit(create_result["file_path"], config)
                else:
                    reply = f"❌ Помилка: {create_result.get('error', 'невідома помилка')}"
            else:
                reply = await _route_and_execute(
                    text, update, context, config, index, stats, provider, vector_store
                )

        await update.message.reply_text(reply)

    except Exception as exc:
        logger.error("_handle_document error: %s", exc)
        from telegram.formatter import format_media_processing_error
        await update.message.reply_text(format_media_processing_error())
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


async def _route_and_execute(
    text: str,
    update,
    context,
    config,
    index,
    stats,
    provider,
    vector_store,
    content_override: str | None = None,
) -> str:
    """Route text through AI semantic router and execute the resulting ActionPlan."""
    from vault_writer.ai.router import route
    from vault_writer.tools.executor import execute
    from telegram.i18n import t

    if not context.bot_data.get("ai_ready", False):
        return t("ai_not_ready")

    try:
        loop = asyncio.get_running_loop()
        plan = await loop.run_in_executor(None, route, text, provider, index)
    except Exception as exc:
        logger.error("media route failed: %s", exc, exc_info=True)
        return f"❌ AI error: `{exc}`"

    # For media with content_override (PDFs), force create_note and inject override
    if content_override is not None:
        from vault_writer.ai.router import Intent
        plan.should_save = True
        if plan.intent not in (
            Intent.CREATE_NOTE, Intent.APPEND_NOTE,
            Intent.UPDATE_NOTE, Intent.EXTRACT_STRUCTURED,
        ):
            plan.intent = Intent.CREATE_NOTE

        from vault_writer.tools.create_note import handle_create_note_from_plan
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, handle_create_note_from_plan,
            text, plan, config, index, stats, provider, vector_store, content_override,
        )
        if result.get("success"):
            from telegram.formatter import format_confirmation, format_similarity_notice
            reply = format_confirmation(result["file_path"])
            notices = result.get("similarity_notices", [])
            if notices:
                reply += "\n\n" + format_similarity_notice(notices)
            if config.git.enabled and config.git.auto_commit:
                _git_commit(result["file_path"], config)
            return reply
        return f"❌ Помилка: {result.get('error', 'невідома помилка')}"

    reply = await execute(
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
    if reply and plan.should_save and config.git.enabled and config.git.auto_commit:
        _git_commit(stats.last_note_path, config)
    return reply or ""


async def _run_create_note(
    text: str,
    note_type,
    folder,
    config,
    index,
    stats,
    provider,
    vector_store=None,
    content_override: str | None = None,
) -> dict:
    loop = asyncio.get_running_loop()
    fn = functools.partial(
        handle_create_note,
        text, note_type, folder, config, index, stats, provider, vector_store,
        content_override=content_override,
    )
    return await loop.run_in_executor(None, fn)


def _git_commit(file_path: str, config) -> None:
    try:
        from git_sync.sync import commit_note
        commit_note(config.vault.path, file_path, config.git)
    except Exception as exc:
        logger.warning("git commit error: %s", exc)
