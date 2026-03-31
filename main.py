"""BrainSync entry point: load config → build vault index → start Telegram bot.

NOTE: The VaultWriter MCP server (vault_writer/server.py) is a SEPARATE process.
It is started by external callers (e.g. Claude Code via mcp_servers.json).
MCP stdio transport owns stdin/stdout — incompatible with PTB run_polling() in the same process.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


async def _ensure_infrastructure_ready(app) -> None:
    """Post-init hook: ensure Whisper model is cached; blocks until download completes."""
    import telegram.handlers.media as _media_mod

    config = app.bot_data["config"]
    model_size = config.media.transcription_model
    allowed_ids = config.telegram.allowed_user_ids

    # Check if model already cached (huggingface hub directory)
    cache_root = Path.home() / ".cache" / "huggingface" / "hub"
    model_cached = any(
        p.is_dir()
        for p in cache_root.glob("*")
        if model_size in p.name
    ) if cache_root.exists() else False

    if not model_cached and allowed_ids:
        logger.info("Whisper model '%s' not found — downloading…", model_size)
        try:
            from telegram.formatter import format_model_downloading
            await app.bot.send_message(chat_id=allowed_ids[0], text=format_model_downloading())
        except Exception as exc:
            logger.warning("Could not send download notification: %s", exc)

    # Instantiate Transcriber (triggers model download if not cached — blocking I/O)
    from vault_writer.ai.transcriber import Transcriber
    import asyncio as _asyncio
    transcriber = Transcriber(model_size=model_size)
    loop = _asyncio.get_running_loop()
    await loop.run_in_executor(None, transcriber._load)  # offload blocking download

    app.bot_data["transcriber"] = transcriber
    _media_mod._READY = True
    logger.info("Whisper model ready: %s", model_size)

    if allowed_ids:
        try:
            from telegram.formatter import format_model_ready
            await app.bot.send_message(chat_id=allowed_ids[0], text=format_model_ready())
        except Exception as exc:
            logger.warning("Could not send ready notification: %s", exc)

    # Start background vault indexing (non-blocking)
    vector_store = app.bot_data.get("vector_store")
    if vector_store is not None:
        import threading
        def _build_index_background():
            try:
                count = vector_store.build_from_vault(config.vault.path, config.embedding)
                logger.info("Background vault indexing complete: %d notes", count)
            except Exception as exc:
                logger.warning("Background vault indexing failed: %s", exc)
        t = threading.Thread(target=_build_index_background, daemon=True, name="vault-indexer")
        t.start()
        logger.info("Background vault indexing started")


def main() -> None:
    config_path = "config.yaml"
    if not Path(config_path).exists():
        print(f"ERROR: {config_path} not found. Run python setup.py first.")
        sys.exit(1)

    from config.loader import SessionStats, get_ai_provider, get_embedding_provider, load_config, setup_logging
    config = load_config(config_path)
    setup_logging(config)
    logger.info("BrainSync starting — mode=%s provider=%s", config.ai.processing_mode, config.ai.provider)

    # Build vault index
    from vault_writer.vault.indexer import build_index
    index = build_index(config.vault.path)
    logger.info("Vault index built: %d notes, %d topics", index.total_notes, len(index.topics))

    # Init session stats
    stats = SessionStats(vault_notes_total=index.total_notes)

    # Init AI provider
    try:
        provider = get_ai_provider(config)
        logger.info("AI provider ready: %s", config.ai.provider)
    except Exception as exc:
        logger.warning("AI provider init failed: %s — running in minimal mode", exc)
        provider = None

    # Init embedding provider + vector store
    from vault_writer.rag.vector_store import VectorStore
    try:
        embedder = get_embedding_provider(config)
        vector_store = VectorStore(config.embedding.index_path, embedder)
        logger.info("VectorStore initialised at %s", config.embedding.index_path)
    except Exception as exc:
        logger.warning("VectorStore init failed: %s — RAG features disabled", exc)
        vector_store = None

    # Start Telegram bot (blocking)
    from telegram.bot import build_application
    app = build_application(config, index, stats, provider, vector_store=vector_store)

    # Infrastructure readiness gate: download Whisper model before accepting messages
    app.post_init = _ensure_infrastructure_ready

    logger.info("Telegram bot starting — allowed_users=%s", config.telegram.allowed_user_ids)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
