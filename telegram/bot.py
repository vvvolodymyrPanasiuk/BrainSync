"""Telegram bot application setup: handler registration and job queue."""
from __future__ import annotations

from datetime import time as _time

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters


def build_application(config, index, stats, provider, vector_store=None) -> Application:
    """Build PTB Application with all handlers and job queue configured."""
    app = (
        Application.builder()
        .token(config.telegram.bot_token)
        .build()
    )

    # Store shared state
    app.bot_data["config"] = config
    app.bot_data["index"] = index
    app.bot_data["stats"] = stats
    app.bot_data["provider"] = provider
    app.bot_data["vector_store"] = vector_store
    app.bot_data["ai_ready"] = False  # set True only after successful warmup in post_init

    # Command handlers
    from telegram.handlers.commands import (
        cmd_clip, cmd_help, cmd_reindex, cmd_reload,
        cmd_settings, cmd_stats, cmd_status, cmd_today,
    )
    app.add_handler(CommandHandler("clip",     cmd_clip))
    app.add_handler(CommandHandler("today",    cmd_today))
    app.add_handler(CommandHandler("stats",    cmd_stats))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CommandHandler("status",   cmd_status))
    app.add_handler(CommandHandler("reload",   cmd_reload))
    app.add_handler(CommandHandler("reindex",  cmd_reindex))
    app.add_handler(CommandHandler("help",     cmd_help))

    # Inline keyboard callback handler
    from telegram.handlers.callbacks import handle_callback
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Plain-text message handler
    from telegram.handlers.message import handle_message
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Media message handlers
    from telegram.handlers.media import handle_media_message
    app.add_handler(MessageHandler(filters.VOICE, handle_media_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_media_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_media_message))

    # Global error handler — prevents "No error handlers registered" log spam
    app.add_error_handler(_error_handler)

    # Scheduled jobs
    _register_scheduled_jobs(app, config)

    return app


async def _error_handler(update, context) -> None:
    """Log PTB errors and notify user if possible."""
    import logging
    logger = logging.getLogger(__name__)
    logger.error("PTB unhandled exception", exc_info=context.error)

    # Try to reply to the user
    if update and hasattr(update, "message") and update.message:
        try:
            from telegram.i18n import t
            await update.message.reply_text(t("ai_unavailable"))
        except Exception:
            pass


def _register_scheduled_jobs(app: Application, config) -> None:
    from telegram.handlers.schedule import (
        daily_summary_job, monthly_summary_job,
        stale_task_reminder_job, weekly_summary_job,
    )

    jq = app.job_queue
    if jq is None:
        return

    if config.schedule.daily_summary_enabled:
        jq.run_daily(daily_summary_job, time=config.schedule.daily_summary_time)

    if config.schedule.weekly_review_enabled:
        # PTB run_daily with days parameter
        _day_map = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6,
        }
        day_num = _day_map.get(config.schedule.weekly_review_day.lower(), 6)
        jq.run_daily(
            weekly_summary_job,
            time=config.schedule.weekly_review_time,
            days=(day_num,),
        )

    if config.schedule.monthly_review_enabled:
        jq.run_monthly(
            monthly_summary_job,
            when=config.schedule.monthly_review_time,
            day=config.schedule.monthly_review_day,
        )

    if config.schedule.stale_task_reminder_enabled:
        jq.run_daily(stale_task_reminder_job, time=config.schedule.stale_task_reminder_time)
