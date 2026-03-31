"""Telegram bot application setup: handler registration and job queue."""
from __future__ import annotations

from datetime import time as _time

from telegram.ext import Application, CommandHandler, MessageHandler, filters


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

    # Command handlers
    from telegram.handlers.commands import (
        cmd_help, cmd_idea, cmd_journal, cmd_mode,
        cmd_note, cmd_reindex, cmd_search, cmd_status, cmd_task,
    )
    app.add_handler(CommandHandler("note", cmd_note))
    app.add_handler(CommandHandler("task", cmd_task))
    app.add_handler(CommandHandler("idea", cmd_idea))
    app.add_handler(CommandHandler("journal", cmd_journal))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("reindex", cmd_reindex))

    # Plain-text message handler
    from telegram.handlers.message import handle_message
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Media message handlers
    from telegram.handlers.media import handle_media_message
    app.add_handler(MessageHandler(filters.VOICE, handle_media_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_media_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_media_message))

    # Scheduled jobs
    _register_scheduled_jobs(app, config)

    return app


def _register_scheduled_jobs(app: Application, config) -> None:
    from telegram.handlers.schedule import daily_summary_job, monthly_summary_job, weekly_summary_job

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
