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
) -> tuple:
    """Execute ActionPlan and return (reply_text, keyboard | None). Never raises."""
    try:
        result = await _execute_inner(
            plan, message, update, context, config, index, stats, provider, vector_store
        )
        # _save_note returns (text, keyboard); all others return plain str
        if isinstance(result, tuple):
            return result
        return result, None
    except Exception as exc:
        logger.error("executor: unhandled error intent=%s: %s", plan.intent.value, exc, exc_info=True)
        from telegram.i18n import t
        return t("ai_unavailable"), None


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
        plan = await _re_route(clarified_message, provider, index, config.vault.language)
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
        return await _chat(message, provider, config, vector_store)

    if intent == Intent.SEARCH_WEB:
        return await _search_web(message, provider, config)

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
        return await _save_note(message, plan, config, index, stats, provider, vector_store, context)

    # Fallback
    logger.warning("executor: unhandled intent %s — treating as create_note", intent.value)
    return await _save_note(message, plan, config, index, stats, provider, vector_store, context)


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


async def _chat(message: str, provider, config=None, vector_store=None) -> str:
    """Chat response: vault check (priority, labeled) + AI general answer (labeled)."""
    from telegram.i18n import t
    if provider is None:
        return t("ai_unavailable")

    # Search vault for relevant context
    vault_snippets = await _vault_snippets(message, vector_store, config)

    if vault_snippets:
        vault_context = "\n\n".join(vault_snippets)
        prompt = (
            f"The user sent a message. Their personal knowledge vault contains these relevant notes:\n\n"
            f"{vault_context}\n\n"
            f"User message: {message}\n\n"
            f"Respond in the SAME LANGUAGE as the user's message in exactly TWO labeled sections:\n"
            f"Section 1 — start with exactly '📚 *Із vault:*' then synthesize what the vault notes say about this.\n"
            f"Section 2 — start with exactly '🤖 *Відповідь ШІ:*' then give your own answer or insight.\n"
            f"Keep each section concise and useful."
        )
    else:
        prompt = (
            f"The user sent a message. Their personal knowledge vault has NO relevant notes on this topic.\n\n"
            f"User message: {message}\n\n"
            f"Respond in the SAME LANGUAGE as the user's message in exactly TWO labeled sections:\n"
            f"Section 1 — start with exactly '📚 *Із vault:*' then write: nothing found in vault.\n"
            f"Section 2 — start with exactly '🤖 *Відповідь ШІ:*' then give your own comprehensive answer.\n"
            f"Keep each section concise and useful."
        )

    loop = asyncio.get_running_loop()
    import time as _time
    logger.info("executor: _chat → sending to AI (vault_hits=%d)…", len(vault_snippets))
    _t0 = _time.monotonic()
    try:
        answer = await loop.run_in_executor(None, provider.complete, prompt)
        logger.info("executor: _chat ← AI replied in %.1fs", _time.monotonic() - _t0)
        return answer.strip()
    except Exception as exc:
        logger.warning("executor: _chat AI call failed after %.1fs: %s", _time.monotonic() - _t0, exc)
        return t("ai_unavailable")


async def _search_web(message: str, provider, config=None) -> str:
    """Ask the AI to search the web for current data and synthesise an answer."""
    from telegram.i18n import t
    if provider is None:
        return t("ai_unavailable")

    prompt = (
        f"Search the web for up-to-date information about the following query. "
        f"Provide a comprehensive answer with real facts and include sources/links where possible.\n\n"
        f"Query: {message}\n\n"
        f"Respond in the SAME LANGUAGE as the query. "
        f"Start your response with '🌐 *Результат пошуку:*' for Ukrainian queries "
        f"or '🌐 *Web search result:*' for English queries. "
        f"If you cannot search the web, answer from your knowledge and note the limitation."
    )

    loop = asyncio.get_running_loop()
    import time as _time
    logger.info("executor: _search_web → sending to AI…")
    _t0 = _time.monotonic()
    try:
        answer = await loop.run_in_executor(None, provider.complete, prompt)
        logger.info("executor: _search_web ← AI replied in %.1fs", _time.monotonic() - _t0)
        answer = answer.strip()
        if not answer.startswith("🌐"):
            answer = "🌐 *Web search result:*\n\n" + answer
        return answer
    except Exception as exc:
        logger.warning("executor: _search_web failed after %.1fs: %s", _time.monotonic() - _t0, exc)
        return t("ai_unavailable")


async def _vault_snippets(message: str, vector_store, config) -> list[str]:
    """Return a list of vault excerpt strings for use in AI prompts. Empty list if nothing found."""
    if vector_store is None:
        return []
    is_ready = getattr(vector_store, "is_ready", None)
    if is_ready is not None and not is_ready():
        return []
    top_k = getattr(getattr(config, "embedding", None), "top_k_results", 5) if config else 5
    try:
        loop = asyncio.get_running_loop()
        fn = getattr(vector_store, "hybrid_search", vector_store.search)
        results = await loop.run_in_executor(None, fn, message, top_k)
        snippets = []
        for r in results:
            path = getattr(r, "file_path", None)
            excerpt = getattr(r, "excerpt", "") or ""
            if path and excerpt.strip():
                snippets.append(f"[{path}]\n{excerpt[:600]}")
        return snippets
    except Exception as exc:
        logger.warning("executor: vault snippet search failed: %s", exc)
        return []


async def _combined_vault_and_web(
    message: str, vector_store, provider, config
) -> str:
    """Search vault + ask AI to search web; return two labeled sections in one call."""
    from telegram.i18n import t
    if provider is None:
        return t("ai_unavailable")

    vault_snippets = await _vault_snippets(message, vector_store, config)

    if vault_snippets:
        vault_context = "\n\n".join(vault_snippets)
        prompt = (
            f"The user has a query. Their personal knowledge vault contains these relevant notes:\n\n"
            f"{vault_context}\n\n"
            f"Query: {message}\n\n"
            f"Please:\n"
            f"1. Search the web for current, up-to-date information on this topic\n"
            f"2. Respond in the SAME LANGUAGE as the query in exactly TWO labeled sections:\n"
            f"   Section 1 — start with exactly '📚 *Із vault:*' then synthesize what the vault notes say\n"
            f"   Section 2 — start with exactly '🌐 *З інтернету:*' then summarize what you found on the web, with sources\n"
            f"Keep each section focused and useful."
        )
    else:
        prompt = (
            f"The user has a query. Their personal knowledge vault has NO relevant notes on this topic.\n\n"
            f"Query: {message}\n\n"
            f"Please:\n"
            f"1. Search the web for current, up-to-date information on this topic\n"
            f"2. Respond in the SAME LANGUAGE as the query in exactly TWO labeled sections:\n"
            f"   Section 1 — start with exactly '📚 *Із vault:*' then write: nothing found in vault\n"
            f"   Section 2 — start with exactly '🌐 *З інтернету:*' then summarize what you found on the web, with sources\n"
            f"Keep each section focused and useful."
        )

    loop = asyncio.get_running_loop()
    import time as _time
    logger.info("executor: _combined_vault_and_web → sending to AI (vault_hits=%d)…", len(vault_snippets))
    _t0 = _time.monotonic()
    try:
        answer = await loop.run_in_executor(None, provider.complete, prompt)
        logger.info("executor: _combined_vault_and_web ← AI replied in %.1fs", _time.monotonic() - _t0)
        return answer.strip()
    except Exception as exc:
        logger.warning("executor: _combined_vault_and_web failed after %.1fs: %s", _time.monotonic() - _t0, exc)
        return t("ai_unavailable")


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
    context=None,
) -> str:
    from vault_writer.tools.create_note import handle_create_note_from_plan
    from telegram.formatter import format_confirmation, format_similarity_notice
    from telegram.i18n import t

    # ── Smart split: try splitting multi-topic messages before saving ─────────
    if provider is not None:
        splits = await _try_split(message, provider)
        if splits:
            logger.info("executor: smart split → %d notes", len(splits))
            replies = [t("split_saved", count=len(splits))]
            for split in splits:
                try:
                    sub_plan = await _re_route(split["text"], provider, index, config.vault.language)
                    sub_plan.title = split["topic"]
                except Exception:
                    sub_plan = plan
                loop = asyncio.get_running_loop()
                r = await loop.run_in_executor(
                    None, handle_create_note_from_plan,
                    split["text"], sub_plan, config, index, stats, provider, vector_store,
                )
                if r.get("success"):
                    replies.append(f"  · {format_confirmation(r['file_path'])}")
            return "\n".join(replies)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, handle_create_note_from_plan,
        message, plan, config, index, stats, provider, vector_store,
    )

    if result.get("success"):
        reply = format_confirmation(result["file_path"])
        notices = result.get("similarity_notices", [])
        has_dup = False

        if notices:
            reply += "\n\n" + format_similarity_notice(notices)
            first_dup = next((n for n in notices if n.is_duplicate), None)
            if first_dup and context is not None and context.user_data is not None:
                context.user_data["pending_merge"] = {
                    "new_path": result["file_path"],
                    "duplicate_path": first_dup.matched_path,
                }
                has_dup = True
                logger.info(
                    "executor: pending merge stored: %s ↔ %s",
                    result["file_path"], first_dup.matched_path,
                )

        # ── Inline keyboard ───────────────────────────────────────────────────
        from telegram.keyboards import duplicate_actions, save_actions
        keyboard = duplicate_actions() if has_dup else save_actions(result["file_path"])
        return reply, keyboard

    return f"❌ Error: {result.get('error', 'unknown error')}", None


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


async def _try_split(message: str, provider) -> list[dict] | None:
    """Detect if message covers multiple unrelated topics and return splits.

    Returns a list of {topic, text} dicts if splitting is warranted (≥2 items),
    otherwise returns None. Only runs for messages longer than 150 chars.
    """
    if len(message) < 150:
        return None

    import json as _json
    import re as _re

    prompt = (
        "Does this message contain 2 or more CLEARLY UNRELATED topics that should be "
        "separate Obsidian notes (e.g. a coding insight + a personal fitness event)?\n"
        "Be conservative — do NOT split if it's one topic with multiple aspects.\n"
        "If yes: return JSON array [{\"topic\": \"...\", \"text\": \"...\"}] (one object per topic).\n"
        "If no: return []\n\n"
        f"Message:\n{message}"
    )
    try:
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(None, provider.complete, prompt, 500)
        raw = _re.sub(r"<think>.*?</think>", "", raw, flags=_re.DOTALL).strip()
        j_start = raw.find("[")
        j_end = raw.rfind("]") + 1
        if j_start == -1 or j_end <= j_start:
            return None
        splits = _json.loads(raw[j_start:j_end])
        if not isinstance(splits, list) or len(splits) < 2:
            return None
        valid = [s for s in splits if isinstance(s, dict) and s.get("topic") and s.get("text")]
        return valid if len(valid) >= 2 else None
    except Exception as exc:
        logger.debug("executor: _try_split: %s", exc)
        return None


async def _re_route(message: str, provider, index, locale: str = "en") -> ActionPlan:
    """Re-route a clarified message through the AI router. Raises on failure."""
    from vault_writer.ai.router import route
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, route, message, provider, index, locale)


def _building_prefix(vector_store) -> str:
    if vector_store is not None and getattr(vector_store, "_building", False):
        from telegram.formatter import format_index_building_notice
        return format_index_building_notice() + "\n\n"
    return ""
