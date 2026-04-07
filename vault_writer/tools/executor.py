"""Action Executor: execute ActionPlan from the AI Semantic Router."""
from __future__ import annotations

import asyncio
import logging

from vault_writer.ai.router import ActionPlan, Intent

logger = logging.getLogger(__name__)

# Key used in context.user_data to track pending clarification
_CLARIFY_KEY = "pending_clarification"


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
    """Execute ActionPlan and return reply string. Never raises — always returns a string."""
    try:
        return await _execute_inner(
            plan, message, update, context, config, index, stats, provider, vector_store
        )
    except Exception as exc:
        logger.error("executor: unhandled error intent=%s: %s", plan.intent.value, exc, exc_info=True)
        from telegram.i18n import t
        return t("ai_unavailable")


async def _execute_inner(
    plan: ActionPlan,
    message: str,
    update,
    context,
    config,
    index,
    stats,
    provider,
    vector_store,
) -> str:
    """Internal dispatcher — may raise; executor() catches all exceptions."""
    intent = plan.intent
    logger.debug("executor: dispatching intent=%s", intent.value)

    # ── Check if user is answering a pending clarification ────────────────────
    pending = context.user_data.get(_CLARIFY_KEY) if context.user_data is not None else None
    if pending and intent not in (Intent.REQUEST_CLARIFICATION, Intent.IGNORE_SPAM):
        # User replied to our clarification question — re-route with full context
        clarified_message = f"{pending['question']}\nUser reply: {message}"
        logger.info("executor: resolving clarification with reply=%r", message[:80])
        context.user_data.pop(_CLARIFY_KEY, None)
        # Re-route the combined clarification context
        plan = await _re_route(clarified_message, provider, index)
        intent = plan.intent

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

    if intent == Intent.SEARCH_WEB:
        return await _search_web(message, provider)

    if intent == Intent.REQUEST_CLARIFICATION:
        return await _clarify(message, plan, provider, context)

    if intent in (Intent.IGNORE_SPAM, Intent.MANUAL_REVIEW):
        logger.info("executor: intent=%s — no reply", intent.value)
        return ""

    if intent == Intent.MOVE_NOTE:
        return await _move_note(message, plan, config, index, vector_store)

    if intent == Intent.APPEND_NOTE:
        return await _append_note(message, plan, config, index, stats, provider, vector_store)

    if intent == Intent.UPDATE_NOTE:
        return await _update_note(message, plan, config, index, stats, provider, vector_store)

    # Save-type intents: CREATE_NOTE, EXTRACT_STRUCTURED, PARSE_DOCUMENT
    if intent in (Intent.CREATE_NOTE, Intent.EXTRACT_STRUCTURED, Intent.PARSE_DOCUMENT):
        return await _save_note(message, plan, config, index, stats, provider, vector_store)

    # Fallback
    logger.warning("executor: unhandled intent %s — treating as create_note", intent.value)
    return await _save_note(message, plan, config, index, stats, provider, vector_store)


# ── Handlers ──────────────────────────────────────────────────────────────────

async def _answer_from_vault(message: str, vector_store, provider, config) -> str:
    from vault_writer.rag.engine import answer_query
    from telegram.formatter import format_rag_answer, format_rag_not_found

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
    """Broad vault analysis: summarise topics and note counts."""
    topic_counts: dict[str, int] = {}
    for note in index.notes.values():
        parts = note.folder.split("/") if note.folder else ["General"]
        top = parts[0] or "General"
        topic_counts[top] = topic_counts.get(top, 0) + 1

    vault_summary = f"Total notes: {index.total_notes}\nTopics:\n"
    for topic, count in sorted(topic_counts.items(), key=lambda x: -x[1]):
        vault_summary += f"  • {topic}: {count} notes\n"

    if provider is not None:
        prompt = (
            f"The user asks: {message}\n\n"
            f"Here is their vault structure:\n{vault_summary}\n"
            "Answer helpfully in the same language as the user's message. "
            "Be specific about what topics exist and how many notes are in each."
        )
        import time as _time
        logger.info("executor: _analyze_vault → sending to AI…")
        _t0 = _time.monotonic()
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, provider.complete, prompt)
        logger.info("executor: _analyze_vault ← AI replied in %.1fs", _time.monotonic() - _t0)
        return result

    return f"📚 Vault overview:\n{vault_summary}"


async def _search_vault(message: str, vector_store, config) -> str:
    from vault_writer.rag.engine import search_vault
    from telegram.formatter import format_semantic_search_results

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
    import time as _time
    logger.info("executor: _chat → sending to AI…")
    _t0 = _time.monotonic()
    try:
        answer = await loop.run_in_executor(None, provider.complete, prompt)
        logger.info("executor: _chat ← AI replied in %.1fs", _time.monotonic() - _t0)
        return format_chat_reply(answer)
    except Exception as exc:
        logger.warning("executor: _chat AI call failed after %.1fs: %s", _time.monotonic() - _t0, exc)
        return t("ai_unavailable")


async def _search_web(message: str, provider) -> str:
    """Search via DuckDuckGo API (no key required), synthesise with AI."""
    try:
        loop = asyncio.get_running_loop()
        snippets = await loop.run_in_executor(None, _ddg_search, message)
    except Exception as exc:
        logger.warning("web search failed: %s", exc)
        snippets = []

    if not snippets:
        if provider is not None:
            prompt = (
                f"Answer the following question from your own knowledge. "
                f"Note that web search was attempted but returned no results.\n\n{message}"
            )
            loop = asyncio.get_running_loop()
            answer = await loop.run_in_executor(None, provider.complete, prompt)
            return f"🌐 (web search unavailable)\n\n{answer}"
        return "🌐 Web search unavailable and no AI provider configured."

    context_text = "\n\n".join(
        f"[{i+1}] {s['title']}\n{s['snippet']}\nSource: {s['url']}"
        for i, s in enumerate(snippets[:5])
    )

    if provider is not None:
        prompt = (
            f"Answer the user's question based on the following web search results. "
            f"Cite sources with [N]. Mark every fact from web as (source: web).\n\n"
            f"Question: {message}\n\nSearch results:\n{context_text}\n\n"
            f"Answer in the same language as the question."
        )
        loop = asyncio.get_running_loop()
        answer = await loop.run_in_executor(None, provider.complete, prompt)
        return f"🌐 *Web search result:*\n\n{answer}"

    # No AI — return raw snippets
    lines = ["🌐 *Web search results:*\n"]
    for i, s in enumerate(snippets[:5], 1):
        lines.append(f"*{i}. {s['title']}*\n{s['snippet']}\n_{s['url']}_\n")
    return "\n".join(lines)


def _ddg_search(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo Instant Answer API — no API key required."""
    import json
    import urllib.parse
    import urllib.request

    url = (
        "https://api.duckduckgo.com/?q="
        + urllib.parse.quote_plus(query)
        + "&format=json&no_html=1&skip_disambig=1"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "BrainSync/1.0"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    results: list[dict] = []

    # Abstract (featured snippet)
    if data.get("AbstractText"):
        results.append({
            "title": data.get("Heading", "DuckDuckGo"),
            "snippet": data["AbstractText"],
            "url": data.get("AbstractURL", "https://duckduckgo.com"),
        })

    # Related topics
    for item in data.get("RelatedTopics", []):
        if len(results) >= max_results:
            break
        if "Text" in item and "FirstURL" in item:
            results.append({
                "title": item.get("Text", "")[:80],
                "snippet": item.get("Text", ""),
                "url": item["FirstURL"],
            })

    return results


async def _clarify(message: str, plan: ActionPlan, provider, context) -> str:
    """Ask a clarifying question and store original message for next turn."""
    if provider is None:
        return "Could you clarify what you mean? / Уточніть, будь ласка."

    prompt = (
        "The user sent an ambiguous message. Ask ONE brief, friendly clarifying question "
        "in the same language as the user's message. Be specific.\n"
        f"Message: {message}\nReason it is ambiguous: {plan.reason}"
    )
    loop = asyncio.get_running_loop()
    question = await loop.run_in_executor(None, provider.complete, prompt)

    # Persist so next message is treated as clarification answer
    if context is not None and context.user_data is not None:
        context.user_data[_CLARIFY_KEY] = {
            "original": message,
            "question": question,
        }
        logger.info("executor: clarification pending, stored for next turn")

    return question


async def _append_note(
    message: str, plan: ActionPlan, config, index, stats, provider, vector_store
) -> str:
    """Find best matching note and append content to it."""
    from pathlib import Path
    from telegram.formatter import format_confirmation

    # Find candidate note via vector search or topic match
    target_path = await _find_target_note(plan, message, vector_store, index, config)

    if target_path is None:
        # No matching note found — create new instead
        logger.info("executor: append_note — no target found, creating new note")
        return await _save_note(message, plan, config, index, stats, provider, vector_store)

    vault = Path(config.vault.path)
    full_path = vault / target_path

    if not full_path.exists():
        logger.warning("executor: append target %s not found on disk", target_path)
        return await _save_note(message, plan, config, index, stats, provider, vector_store)

    try:
        existing = full_path.read_text(encoding="utf-8")

        # Format the new content to append
        if provider is not None:
            loop = asyncio.get_running_loop()
            append_text = await loop.run_in_executor(
                None, provider.complete,
                f"Format this content as a clean markdown addition to an existing note.\n"
                f"Just return the formatted content, no explanation.\n\n{message}",
            )
        else:
            append_text = message

        separator = "\n\n---\n\n" if not existing.rstrip().endswith("---") else "\n\n"
        updated = existing.rstrip() + separator + append_text.strip() + "\n"
        full_path.write_text(updated, encoding="utf-8")

        if vector_store is not None:
            try:
                vector_store.upsert_note(target_path, updated)
            except Exception as exc:
                logger.warning("vector upsert after append: %s", exc)

        logger.info("executor: appended to %s", target_path)
        return f"✏️ Appended to `{target_path}`"
    except Exception as exc:
        logger.error("executor: append_note failed: %s", exc)
        return f"❌ Could not append: {exc}"


async def _update_note(
    message: str, plan: ActionPlan, config, index, stats, provider, vector_store
) -> str:
    """Find best matching note and rewrite its content body."""
    from pathlib import Path

    target_path = await _find_target_note(plan, message, vector_store, index, config)

    if target_path is None:
        logger.info("executor: update_note — no target found, creating new note")
        return await _save_note(message, plan, config, index, stats, provider, vector_store)

    vault = Path(config.vault.path)
    full_path = vault / target_path

    if not full_path.exists():
        return await _save_note(message, plan, config, index, stats, provider, vector_store)

    try:
        existing = full_path.read_text(encoding="utf-8")

        # Preserve frontmatter, replace body
        if existing.startswith("---"):
            end = existing.find("---", 3)
            if end != -1:
                frontmatter = existing[: end + 3]
                old_body = existing[end + 3:]
            else:
                frontmatter = ""
                old_body = existing
        else:
            frontmatter = ""
            old_body = existing

        if provider is not None:
            loop = asyncio.get_running_loop()
            new_body = await loop.run_in_executor(
                None, provider.complete,
                f"Update the following note body with new information. "
                f"Preserve structure. Return only the updated body.\n\n"
                f"EXISTING BODY:\n{old_body}\n\nNEW INFORMATION:\n{message}",
            )
        else:
            new_body = f"{old_body}\n\n### Update\n\n{message}"

        updated = (frontmatter + "\n" + new_body.strip() + "\n") if frontmatter else (new_body.strip() + "\n")
        full_path.write_text(updated, encoding="utf-8")

        if vector_store is not None:
            try:
                vector_store.upsert_note(target_path, updated)
            except Exception as exc:
                logger.warning("vector upsert after update: %s", exc)

        logger.info("executor: updated %s", target_path)
        return f"✅ Updated `{target_path}`"
    except Exception as exc:
        logger.error("executor: update_note failed: %s", exc)
        return f"❌ Could not update: {exc}"


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


async def _move_note(
    message: str,
    plan: ActionPlan,
    config,
    index,
    vector_store,
) -> str:
    """Move an existing note to a different vault folder."""
    from pathlib import Path
    from vault_writer.vault.writer import create_moc_if_missing, update_moc
    from vault_writer.vault.indexer import update_index

    vault = Path(config.vault.path)

    # Destination folder comes from the router plan
    dest_folder = plan.target_folder or ""
    dest_subfolder = plan.target_subfolder or ""
    if not dest_folder or dest_folder.lower() == "general":
        return (
            "❌ Не вдалося визначити папку призначення.\n"
            "Вкажіть точніше, наприклад: *перемісти нотатку про лазанью у папку Кулінарія*"
        )

    full_dest = f"{dest_folder}/{dest_subfolder}".rstrip("/") if dest_subfolder else dest_folder

    # Find source note via vector search (semantic match on the message)
    source_path: str | None = None
    if vector_store is not None:
        try:
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(None, vector_store.search, message, 3)
            if results:
                source_path = results[0].file_path
        except Exception as exc:
            logger.warning("executor: vector search for move source: %s", exc)

    # Fallback: topic folder match
    if source_path is None:
        source_path = await _find_target_note(plan, message, None, index, config)

    if source_path is None:
        return "❌ Нотатку не знайдено. Уточніть тему або назву нотатки."

    src = vault / source_path
    if not src.exists():
        return f"❌ Файл не знайдено: `{source_path}`"

    # Path traversal guard
    try:
        (vault / full_dest).resolve().relative_to(vault.resolve())
    except ValueError:
        return "❌ Недопустимий шлях призначення."

    dest_data_dir = vault / full_dest / "_data"
    dest_data_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_data_dir / src.name
    new_rel = f"{full_dest}/_data/{src.name}"

    if dest.resolve() == src.resolve():
        return "ℹ️ Нотатка вже знаходиться в цій папці."
    if dest.exists():
        return f"❌ Файл вже існує в папці призначення: `{new_rel}`"

    # Move
    src.rename(dest)
    logger.info("executor: moved %s → %s", source_path, new_rel)

    # Update vector store
    if vector_store is not None:
        try:
            content = dest.read_text(encoding="utf-8")
            vector_store.delete_note(source_path)
            vector_store.upsert_note(new_rel, content)
        except Exception as exc:
            logger.warning("executor: vector store update after move: %s", exc)

    # Update in-memory index
    old_note = index.notes.pop(source_path, None)
    if old_note is not None:
        old_note.file_path = new_rel
        old_note.folder = full_dest
        index.notes[new_rel] = old_note
        update_index(index, old_note)

    # Create MOC in new folder and link the note
    if config.enrichment_update_moc and old_note is not None:
        try:
            moc_path = create_moc_if_missing(dest_folder, config.vault.path)
            update_moc(moc_path, new_rel, config.vault.path)
        except Exception as exc:
            logger.warning("executor: update_moc after move: %s", exc)

    return f"✅ Переміщено:\n`{source_path}`\n→ `{new_rel}`"


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _find_target_note(plan: ActionPlan, message: str, vector_store, index, config) -> str | None:
    """Find the most relevant existing note path for append/update operations."""
    # 1. Vector similarity search
    if vector_store is not None:
        try:
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(
                None, vector_store.search, message,
                config.embedding.top_k_results,
            )
            if results:
                top = results[0]
                similarity = getattr(top, "similarity", 0) or getattr(top, "distance", 0)
                path = getattr(top, "path", None) or getattr(top, "id", None)
                if path and similarity >= 0.60:
                    logger.info("executor: target note via vector search: %s (%.2f)", path, similarity)
                    return path
        except Exception as exc:
            logger.warning("executor: vector search for target failed: %s", exc)

    # 2. Topic folder match — pick the most recent note in target_folder
    folder = plan.target_folder
    if folder:
        candidates = [
            (path, note) for path, note in index.notes.items()
            if note.folder.split("/")[0].lower() == folder.lower()
        ]
        if candidates:
            # Sort by note_number descending (most recent)
            candidates.sort(key=lambda x: x[1].note_number, reverse=True)
            path = candidates[0][0]
            logger.info("executor: target note via folder match: %s", path)
            return path

    return None


async def _re_route(message: str, provider, index) -> ActionPlan:
    """Re-route a clarified message through the AI router. Raises on failure."""
    from vault_writer.ai.router import route
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, route, message, provider, index)


def _building_prefix(vector_store) -> str:
    if vector_store is not None and getattr(vector_store, "_building", False):
        from telegram.formatter import format_index_building_notice
        return format_index_building_notice() + "\n\n"
    return ""
