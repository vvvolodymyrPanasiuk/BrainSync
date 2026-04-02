"""Action Executor: execute ActionPlan from the AI Semantic Router."""
from __future__ import annotations

import asyncio
import logging

from vault_writer.ai.router import ActionPlan, Intent

logger = logging.getLogger(__name__)


async def execute(
    plan: ActionPlan,
    message: str,
    update,       # telegram.Update
    context,      # ContextTypes.DEFAULT_TYPE
    config,
    index,
    stats,
    provider,
    vector_store,
) -> str:
    """Execute ActionPlan and return reply string. Empty string = no reply."""
    intent = plan.intent
    logger.debug("executor: dispatching intent=%s", intent.value)

    if intent == Intent.ANSWER_FROM_VAULT:
        return await _answer_from_vault(message, vector_store, provider, config)

    if intent == Intent.ANALYZE_VAULT:
        return await _analyze_vault(message, provider, index)

    if intent == Intent.SUMMARIZE_VAULT:
        return await _answer_from_vault(message, vector_store, provider, config)

    if intent == Intent.SEARCH_VAULT:
        return await _search_vault(message, vector_store, config)

    if intent == Intent.CHAT_ONLY:
        return await _chat(message, provider)

    if intent == Intent.REQUEST_CLARIFICATION:
        return await _clarify(message, plan, provider)

    if intent in (Intent.IGNORE_SPAM, Intent.MANUAL_REVIEW):
        logger.info("executor: intent=%s — no reply", intent.value)
        return ""

    # Save-type intents
    if intent in (
        Intent.CREATE_NOTE, Intent.APPEND_NOTE, Intent.UPDATE_NOTE,
        Intent.EXTRACT_STRUCTURED, Intent.PARSE_DOCUMENT,
    ):
        return await _save_note(message, plan, config, index, stats, provider, vector_store)

    logger.warning("executor: unhandled intent %s — treating as create_note", intent.value)
    return await _save_note(message, plan, config, index, stats, provider, vector_store)


# ── Handlers ──────────────────────────────────────────────────────────────────

async def _answer_from_vault(message: str, vector_store, provider, config) -> str:
    from vault_writer.rag.engine import answer_query
    from telegram.formatter import format_rag_answer, format_rag_not_found, format_index_building_notice

    prefix = _building_prefix(vector_store)
    if vector_store is None:
        return prefix + format_rag_not_found()

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, answer_query, message, vector_store, provider,
        config.embedding.top_k_results, config,
    )
    if result.found:
        return prefix + format_rag_answer(result.answer, result.sources)
    return prefix + format_rag_not_found()


async def _analyze_vault(message: str, provider, index) -> str:
    """Broad vault analysis: topics, counts, structure."""
    from telegram.formatter import format_index_building_notice

    topic_counts: dict[str, int] = {}
    for note in index.notes.values():
        parts = note.folder.split("/") if note.folder else ["General"]
        top = parts[0]
        topic_counts[top] = topic_counts.get(top, 0) + 1

    vault_summary = f"Total notes: {index.total_notes}\nTopics:\n"
    for topic, count in sorted(topic_counts.items(), key=lambda x: -x[1]):
        vault_summary += f"  • {topic}: {count} notes\n"

    if provider is not None:
        prompt = (
            f"The user asks: {message}\n\n"
            f"Here is their vault structure:\n{vault_summary}\n"
            "Answer helpfully in the same language as the user's message."
        )
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, provider.complete, prompt)

    return f"📚 Vault overview:\n{vault_summary}"


async def _search_vault(message: str, vector_store, config) -> str:
    from vault_writer.rag.engine import search_vault
    from telegram.formatter import format_semantic_search_results, format_index_building_notice

    prefix = _building_prefix(vector_store)
    if vector_store is None:
        return prefix + "Search unavailable."

    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(
        None, search_vault, message, vector_store, config.embedding.top_k_results,
    )
    return prefix + format_semantic_search_results(results, message)


async def _chat(message: str, provider) -> str:
    from telegram.formatter import format_chat_reply
    from telegram.i18n import t
    if provider is None:
        return t("ai_unavailable")
    prompt = f"Respond in the same language as the user's message.\n\nUser: {message}"
    loop = asyncio.get_running_loop()
    answer = await loop.run_in_executor(None, provider.complete, prompt)
    return format_chat_reply(answer)


async def _clarify(message: str, plan: ActionPlan, provider) -> str:
    if provider is None:
        return "Could you clarify what you mean? / Уточніть, будь ласка."
    prompt = (
        f"The user sent an ambiguous message. Ask a brief, friendly clarifying question "
        f"in the same language.\nMessage: {message}\nReason: {plan.reason}"
    )
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, provider.complete, prompt)


async def _save_note(
    message: str,
    plan: ActionPlan,
    config,
    index,
    stats,
    provider,
    vector_store,
) -> str:
    from vault_writer.tools.create_note import handle_create_note_from_plan
    from telegram.formatter import format_confirmation, format_similarity_notice

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, handle_create_note_from_plan,
        message, plan, config, index, stats, provider, vector_store,
    )

    if result.get("success"):
        reply = format_confirmation(result["file_path"])
        notices = result.get("similarity_notices", [])
        if notices:
            reply += "\n\n" + format_similarity_notice(notices)
        return reply
    return f"❌ Error: {result.get('error', 'unknown error')}"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _building_prefix(vector_store) -> str:
    if vector_store is not None and getattr(vector_store, "_building", False):
        from telegram.formatter import format_index_building_notice
        return format_index_building_notice() + "\n\n"
    return ""
