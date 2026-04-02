"""Standalone bot process — launched in its own console window by the dashboard."""
from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# ── PID file: kill any stale previous instance ────────────────────────────────

_PID_FILE = Path("bot_runner.pid")


def _write_pid() -> None:
    _PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def _clear_pid() -> None:
    try:
        _PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def _kill_stale() -> None:
    """If a PID file exists and that process is still running, kill it."""
    if not _PID_FILE.exists():
        return
    try:
        old_pid = int(_PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        _PID_FILE.unlink(missing_ok=True)
        return
    if old_pid == os.getpid():
        return
    try:
        if sys.platform == "win32":
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x0001, False, old_pid)
            if handle:
                ctypes.windll.kernel32.TerminateProcess(handle, 1)
                ctypes.windll.kernel32.CloseHandle(handle)
        else:
            os.kill(old_pid, signal.SIGTERM)
        import time as _time
        _time.sleep(1)
        logger.info("Killed stale bot process PID=%d", old_pid)
    except Exception:
        pass  # already gone — that's fine
    _PID_FILE.unlink(missing_ok=True)


# ── Windows console: UTF-8 + window title ────────────────────────────────────
if sys.platform == "win32":
    os.system("chcp 65001 > nul 2>&1")
    os.system("title BrainSync Bot")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ── PTB lifecycle hooks ───────────────────────────────────────────────────────

async def _ensure_infrastructure_ready(app) -> None:
    """Post-init: download Whisper model, start vault indexing, notify online."""
    import telegram.handlers.media as _media_mod
    import asyncio as _asyncio

    config = app.bot_data["config"]
    model_size = config.media.transcription_model
    allowed_ids = config.telegram.allowed_user_ids

    # Whisper model cache check
    cache_root = Path.home() / ".cache" / "huggingface" / "hub"
    model_cached = (
        any(p.is_dir() for p in cache_root.glob("*") if model_size in p.name)
        if cache_root.exists() else False
    )
    if not model_cached and allowed_ids:
        logger.info("Whisper model '%s' not cached — downloading…", model_size)
        try:
            from telegram.formatter import format_model_downloading
            await app.bot.send_message(chat_id=allowed_ids[0], text=format_model_downloading())
        except Exception as exc:
            logger.warning("Could not send download notice: %s", exc)

    from vault_writer.ai.transcriber import Transcriber
    transcriber = Transcriber(model_size=model_size)
    loop = _asyncio.get_running_loop()
    await loop.run_in_executor(None, transcriber._load)
    app.bot_data["transcriber"] = transcriber
    _media_mod._READY = True
    logger.info("Whisper model ready: %s", model_size)

    if allowed_ids:
        try:
            from telegram.formatter import format_model_ready
            await app.bot.send_message(chat_id=allowed_ids[0], text=format_model_ready())
        except Exception as exc:
            logger.warning("Could not send ready notice: %s", exc)

    # Background vault indexing (non-blocking)
    vector_store = app.bot_data.get("vector_store")
    if vector_store is not None:
        def _build():
            try:
                count = vector_store.build_from_vault(config.vault.path, config.embedding)
                logger.info("Vault indexing complete: %d notes", count)
            except Exception as exc:
                logger.warning("Vault indexing failed: %s", exc)
        threading.Thread(target=_build, daemon=True, name="vault-indexer").start()
        logger.info("Background vault indexing started")

    # AI warmup — load model into memory before declaring ready
    provider = app.bot_data.get("provider")
    if provider is not None and config.ai.provider == "ollama":
        if allowed_ids:
            try:
                await app.bot.send_message(
                    chat_id=allowed_ids[0],
                    text="⏳ Loading AI model into memory… (cold start, please wait)",
                )
            except Exception:
                pass
        logger.info("AI warmup starting for provider=%s model=%s", config.ai.provider, config.ai.model)
        try:
            await loop.run_in_executor(None, provider.warmup)
            logger.info("AI warmup complete")
        except Exception as exc:
            logger.warning("AI warmup failed: %s — bot will still start, first request may be slow", exc)
            if allowed_ids:
                try:
                    await app.bot.send_message(
                        chat_id=allowed_ids[0],
                        text=f"⚠️ AI warmup failed: {exc}\nBot started but first response may be slow.",
                    )
                except Exception:
                    pass

    # Online notification — sent only after AI is ready
    if allowed_ids:
        from telegram.formatter import format_bot_online
        for uid in allowed_ids:
            try:
                await app.bot.send_message(chat_id=uid, text=format_bot_online())
            except Exception as exc:
                logger.warning("Online notice failed for %s: %s", uid, exc)


async def _notify_shutdown(app) -> None:
    """Post-shutdown: send offline notice to all allowed users."""
    config = app.bot_data.get("config")
    if config is None:
        return
    from telegram.formatter import format_bot_offline
    for uid in config.telegram.allowed_user_ids:
        try:
            await app.bot.send_message(chat_id=uid, text=format_bot_offline())
        except Exception as exc:
            logger.warning("Offline notice failed for %s: %s", uid, exc)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    # Kill any leftover bot instance before starting
    _kill_stale()
    _write_pid()
    import atexit
    atexit.register(_clear_pid)

    from config.loader import (
        SessionStats, get_ai_provider, get_embedding_provider,
        load_config, setup_logging,
    )

    config = load_config("config.yaml")
    setup_logging(config)

    from telegram.i18n import set_locale
    set_locale(config.locale)

    logger.info(
        "BrainSync starting — provider=%s mode=%s locale=%s",
        config.ai.provider, config.ai.processing_mode, config.locale,
    )

    # Vault index
    from vault_writer.vault.indexer import build_index
    index = build_index(config.vault.path)
    logger.info("Vault index: %d notes, %d topics", index.total_notes, len(index.topics))

    stats = SessionStats(vault_notes_total=index.total_notes)

    # AI provider
    try:
        provider = get_ai_provider(config)
        logger.info("AI provider ready: %s", config.ai.provider)
    except Exception as exc:
        logger.warning("AI provider init failed: %s — minimal mode", exc)
        provider = None

    # Vector store
    from vault_writer.rag.vector_store import VectorStore
    try:
        embedder = get_embedding_provider(config)
        vector_store = VectorStore(config.embedding.index_path, embedder)
        logger.info("VectorStore initialised at %s", config.embedding.index_path)
    except Exception as exc:
        logger.warning("VectorStore init failed: %s — RAG disabled", exc)
        vector_store = None

    # Build and run app
    from telegram.bot import build_application
    app = build_application(config, index, stats, provider, vector_store=vector_store)
    app.post_init = _ensure_infrastructure_ready
    app.post_shutdown = _notify_shutdown

    logger.info("Polling — allowed_users=%s", config.telegram.allowed_user_ids)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
