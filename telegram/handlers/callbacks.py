"""CallbackQueryHandler — handles all inline keyboard button presses."""
from __future__ import annotations

import logging
from datetime import time as _time

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# ── YAML key → config path mapping ───────────────────────────────────────────
_YAML_PATHS: dict[str, list[str]] = {
    "git.auto_commit":                 ["git", "auto_commit"],
    "enrichment_add_wikilinks":        ["enrichment", "add_wikilinks"],
    "enrichment_update_moc":           ["enrichment", "update_moc"],
    "schedule.daily_summary_enabled":  ["schedule", "daily_summary", "enabled"],
    "schedule.daily_summary_time":     ["schedule", "daily_summary", "time"],
    "schedule.weekly_review_enabled":  ["schedule", "weekly_review", "enabled"],
    "schedule.weekly_review_time":     ["schedule", "weekly_review", "time"],
    "schedule.monthly_review_enabled": ["schedule", "monthly_review", "enabled"],
    "schedule.monthly_review_time":    ["schedule", "monthly_review", "time"],
    "ai.provider":                     ["ai", "provider"],
    "ai.model":                        ["ai", "model"],
    "locale":                          ["locale"],
}

_BOOL_TOGGLES: dict[str, tuple[str | None, str]] = {
    "git.auto_commit":                 ("git",      "auto_commit"),
    "enrichment_add_wikilinks":        (None,       "enrichment_add_wikilinks"),
    "enrichment_update_moc":           (None,       "enrichment_update_moc"),
    "schedule.daily_summary_enabled":  ("schedule", "daily_summary_enabled"),
    "schedule.weekly_review_enabled":  ("schedule", "weekly_review_enabled"),
    "schedule.monthly_review_enabled": ("schedule", "monthly_review_enabled"),
}

_TEXT_PROMPTS: dict[str, str] = {
    "schedule.daily_summary_time":  "📅 Daily summary time — send HH:MM (e.g. 21:00):",
    "schedule.weekly_review_time":  "📅 Weekly review time — send HH:MM (e.g. 20:00):",
    "schedule.monthly_review_time": "📅 Monthly review time — send HH:MM (e.g. 10:00):",
    "ai.model":                     "🤖 Send the model name (e.g. claude-sonnet-4-6):",
}


def _setting_page(key: str) -> str:
    if key.startswith("schedule."): return "schedules"
    if key.startswith("ai."):       return "ai"
    if key == "locale":             return "language"
    return "notes"


def _persist_yaml(config_path: str, parts: list[str], value) -> None:
    import yaml
    from pathlib import Path
    p = Path(config_path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    node = raw
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value
    p.write_text(yaml.dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _apply_string_setting(config, key: str, value: str) -> None:
    if key == "ai.provider":
        config.ai.provider = value
    elif key == "ai.model":
        config.ai.model = value
    elif key == "locale":
        config.locale = value
        from telegram.i18n import set_locale
        set_locale(value)


async def _show_settings_page(query, config, page: str) -> None:
    from telegram.keyboards import (
        settings_main_keyboard, settings_notes_keyboard,
        settings_schedules_keyboard, settings_ai_keyboard,
        settings_language_keyboard,
    )
    from telegram.i18n import t

    _PAGES = {
        "main":      (lambda: settings_main_keyboard(),        "settings_header"),
        "notes":     (lambda: settings_notes_keyboard(config), "settings_notes_header"),
        "schedules": (lambda: settings_schedules_keyboard(config), "settings_schedules_header"),
        "ai":        (lambda: settings_ai_keyboard(config),    "settings_ai_header"),
        "language":  (lambda: settings_language_keyboard(config), "settings_language_header"),
    }
    if page not in _PAGES:
        page = "main"
    kb_fn, text_key = _PAGES[page]
    await query.edit_message_text(t(text_key), reply_markup=kb_fn(), parse_mode="Markdown")


# ── Main dispatcher ───────────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data: str = query.data or ""

    # ── Duplicate-note actions ─────────────────────────────────────────────────
    if data == "dup_keep":
        context.user_data.pop("pending_merge", None)
        await query.edit_message_reply_markup(reply_markup=None)
        return

    if data == "dup_merge":
        from telegram.handlers.commands import cmd_merge
        await cmd_merge(update, context)
        await query.edit_message_reply_markup(reply_markup=None)
        return

    # ── Merge confirmation ─────────────────────────────────────────────────────
    if data == "merge_do_confirm":
        from telegram.handlers.commands import _do_merge
        await _do_merge(update, context)
        return

    if data == "merge_do_cancel":
        context.user_data.pop("pending_merge", None)
        await query.edit_message_reply_markup(reply_markup=None)
        from telegram.i18n import t
        await query.message.reply_text(t("merge_cancelled"))
        return

    # ── Settings ───────────────────────────────────────────────────────────────
    if data.startswith("settings:"):
        await _handle_settings(update, context, data[9:])
        return

    # ── Post-save actions ──────────────────────────────────────────────────────
    if data.startswith("move:"):
        file_path = data[5:]
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"📁 Send destination folder for:\n`{file_path}`\n\nExample: `Finance/Trading`",
            parse_mode="Markdown",
        )
        context.user_data["pending_move_path"] = file_path
        return

    if data.startswith("tags:"):
        file_path = data[5:]
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"🏷️ Send tags (space-separated) for:\n`{file_path}`\n\nExample: `python async`",
            parse_mode="Markdown",
        )
        context.user_data["pending_tags_path"] = file_path
        return

    # ── YouTube session actions ────────────────────────────────────────────────
    if data == "yt_save":
        from telegram.handlers.youtube_chat import preview_save
        await query.edit_message_reply_markup(reply_markup=None)
        await preview_save(update, context)
        return

    if data == "yt_save_confirm":
        from telegram.handlers.youtube_chat import confirm_save
        await confirm_save(update, context)
        return

    if data == "yt_save_edit":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "✏️ Send your edited note content and I'll save it to the vault."
        )
        context.user_data["yt_waiting_edit"] = True
        return

    if data == "yt_end":
        from telegram.handlers.youtube_chat import end_session
        await end_session(update, context)
        return

    # ── Save RAG/chat insight as a vault note ─────────────────────────────────
    if data == "insight_save":
        await query.edit_message_reply_markup(reply_markup=None)
        insight_text = context.user_data.pop("last_insight", None)
        if not insight_text:
            await query.message.reply_text("❌ Текст відповіді вже недоступний.")
            return
        config       = context.bot_data["config"]
        index        = context.bot_data["index"]
        stats        = context.bot_data["stats"]
        provider     = context.bot_data.get("provider")
        vector_store = context.bot_data.get("vector_store")
        import asyncio
        from vault_writer.tools.create_note import handle_create_note
        from vault_writer.vault.writer import NoteType
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, handle_create_note,
            insight_text, NoteType.NOTE, None,
            config, index, stats, provider, vector_store,
        )
        if result.get("success"):
            from telegram.formatter import format_confirmation
            await query.message.reply_text(format_confirmation(result["file_path"]))
            if config.git.enabled and config.git.auto_commit:
                try:
                    from git_sync.sync import commit_note
                    commit_note(config.vault.path, result["file_path"], config.git)
                except Exception:
                    pass
        else:
            await query.message.reply_text(f"❌ Помилка збереження: {result.get('error')}")
        return

    if data == "insight_discard":
        context.user_data.pop("last_insight", None)
        await query.edit_message_reply_markup(reply_markup=None)
        return

    # ── Lint actions ──────────────────────────────────────────────────────────
    if data == "lint_create_moc":
        await _lint_create_moc(update, context)
        return

    if data == "lint_enrich_isolated":
        await _lint_enrich_isolated(update, context)
        return

    if data == "lint_show_orphans":
        await _lint_show_orphans(update, context)
        return

    if data == "lint_show_stale":
        await _lint_show_stale(update, context)
        return

    if data == "lint_contradictions":
        await _lint_contradictions(update, context)
        return

    logger.debug("callbacks: unhandled data=%r", data)


# ── Settings handler ──────────────────────────────────────────────────────────

async def _handle_settings(update, context, sub: str) -> None:
    query = update.callback_query
    config = context.bot_data["config"]
    from telegram.i18n import t

    # Close
    if sub == "close":
        await query.edit_message_reply_markup(reply_markup=None)
        return

    # Page navigation
    if sub.startswith("page:"):
        page = sub[5:]
        await _show_settings_page(query, config, page)
        return

    # Toggle boolean setting
    if sub.startswith("toggle:"):
        key = sub[7:]
        if key not in _BOOL_TOGGLES:
            await query.answer("Unknown setting.")
            return
        section, attr = _BOOL_TOGGLES[key]
        obj = getattr(config, section) if section else config
        new_val = not getattr(obj, attr)
        setattr(obj, attr, new_val)
        _persist_yaml(config.config_path, _YAML_PATHS[key], new_val)
        await _show_settings_page(query, config, _setting_page(key))
        await query.answer(t("settings_saved", key=attr, value=new_val))
        return

    # Set string value (provider, locale)
    if sub.startswith("set:"):
        rest = sub[4:]
        key, value = rest.rsplit(":", 1)
        _apply_string_setting(config, key, value)
        _persist_yaml(config.config_path, _YAML_PATHS[key], value)
        await _show_settings_page(query, config, _setting_page(key))
        if key in ("ai.provider", "ai.model"):
            await query.answer("⚠️ Restart bot to apply AI changes")
        else:
            await query.answer("✅")
        return

    # Prompt user to type a value
    if sub.startswith("ask:"):
        key = sub[4:]
        context.user_data["pending_settings_input"] = key
        prompt = _TEXT_PROMPTS.get(key, "Send value:")
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(prompt)
        return


# ── Lint action handlers ──────────────────────────────────────────────────────

async def _lint_create_moc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create MoC files for all topics reported as missing."""
    query = update.callback_query
    await query.edit_message_reply_markup(reply_markup=None)

    report = context.user_data.get("lint_report", {})
    topics = report.get("topics_no_moc", [])
    if not topics:
        await query.message.reply_text("Немає тем без MoC.")
        return

    config = context.bot_data["config"]
    from vault_writer.vault.writer import create_moc_if_missing
    created = []
    for topic in topics:
        try:
            path = create_moc_if_missing(topic, config.vault.path)
            created.append(f"  · `{path}`")
            logger.info("lint: created MoC for %s → %s", topic, path)
        except Exception as exc:
            logger.warning("lint: MoC creation failed for %s: %s", topic, exc)

    if created:
        await query.message.reply_text(
            f"✅ Створено {len(created)} MoC:\n" + "\n".join(created),
            parse_mode="Markdown",
        )
        if config.git.enabled and config.git.auto_commit:
            try:
                from git_sync.sync import commit_note
                for path in created:
                    raw = path.strip().strip("`")
                    commit_note(config.vault.path, raw, config.git)
            except Exception:
                pass
    else:
        await query.message.reply_text("❌ Не вдалось створити жодного MoC.")


async def _lint_enrich_isolated(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run AI wikilink enrichment on isolated notes (those with no outgoing links)."""
    query = update.callback_query
    await query.edit_message_reply_markup(reply_markup=None)

    report   = context.user_data.get("lint_report", {})
    isolated = report.get("isolated", [])
    if not isolated:
        await query.message.reply_text("Немає ізольованих нотаток.")
        return

    provider     = context.bot_data.get("provider")
    vector_store = context.bot_data.get("vector_store")
    config       = context.bot_data["config"]
    index        = context.bot_data["index"]

    if provider is None:
        await query.message.reply_text("❌ AI provider недоступний.")
        return

    progress = await query.message.reply_text(
        f"🔗 Додаю wikilinks до {len(isolated)} ізольованих нотаток…"
    )

    import asyncio
    from pathlib import Path
    from vault_writer.ai.linker import enrich_with_links

    vault = Path(config.vault.path)
    enriched, failed = 0, 0

    for rel_path in isolated:
        fp = vault / rel_path
        if not fp.exists():
            continue
        try:
            original = fp.read_text(encoding="utf-8")
            loop = asyncio.get_running_loop()
            enriched_content = await loop.run_in_executor(
                None, enrich_with_links,
                original, index, vector_store, provider, config, rel_path,
            )
            if enriched_content != original:
                fp.write_text(enriched_content, encoding="utf-8")
                if vector_store:
                    vector_store.upsert_note(rel_path, enriched_content)
                enriched += 1
        except Exception as exc:
            logger.warning("lint enrich isolated: %s → %s", rel_path, exc)
            failed += 1

    await progress.delete()
    msg = f"✅ Збагачено {enriched} нотаток wikilinks."
    if failed:
        msg += f" ({failed} помилок)"
    await query.message.reply_text(msg)


async def _lint_show_orphans(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show content of orphaned notes (no incoming links) for manual review."""
    query = update.callback_query
    await query.edit_message_reply_markup(reply_markup=None)

    report  = context.user_data.get("lint_report", {})
    orphans = report.get("orphans", [])
    if not orphans:
        await query.message.reply_text("Немає orphaned нотаток.")
        return

    config = context.bot_data["config"]
    from pathlib import Path
    vault = Path(config.vault.path)

    lines = [f"👁 *Orphaned нотатки* ({len(orphans)}) — ніхто не посилається:\n"]
    for rel_path in orphans[:10]:
        fp = vault / rel_path
        name = Path(rel_path).name
        excerpt = ""
        if fp.exists():
            try:
                content = fp.read_text(encoding="utf-8", errors="replace")
                # Skip frontmatter
                if content.startswith("---"):
                    end = content.find("---", 3)
                    content = content[end + 3:].strip() if end != -1 else content
                excerpt = content[:120].replace("\n", " ").strip()
            except Exception:
                pass
        lines.append(f"📄 `{name}`")
        if excerpt:
            lines.append(f"   _{excerpt}…_")
        lines.append("")

    if len(orphans) > 10:
        lines.append(f"_… ще {len(orphans) - 10} нотаток_")

    lines.append("\n💡 Для кожної: перемісти, злий з іншою або видали вручну.")
    await query.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def _lint_show_stale(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show notes that haven't been updated in > 180 days."""
    query = update.callback_query
    await query.edit_message_reply_markup(reply_markup=None)

    report = context.user_data.get("lint_report", {})
    stale  = report.get("stale", [])
    if not stale:
        await query.message.reply_text("Немає застарілих нотаток.")
        return

    config = context.bot_data["config"]
    index  = context.bot_data["index"]
    from pathlib import Path

    lines = [f"🕰 *Застарілі нотатки* ({len(stale)}) — старші 180 днів:\n"]
    for rel_path in stale[:15]:
        note = index.notes.get(rel_path)
        title = note.title if note else Path(rel_path).stem
        date  = note.date  if note else "?"
        lines.append(f"  · `{date}` — {title}")

    if len(stale) > 15:
        lines.append(f"\n_… ще {len(stale) - 15}_")

    lines.append(
        "\n💡 Розгляни: переглянь кожну нотатку, оновіть висновки або видали якщо неактуальна."
    )
    await query.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def _lint_contradictions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """AI-powered contradiction scan across the vault's largest topic folders."""
    query    = update.callback_query
    provider = context.bot_data.get("provider")
    config   = context.bot_data["config"]
    index    = context.bot_data["index"]

    await query.edit_message_reply_markup(reply_markup=None)

    if provider is None:
        await query.message.reply_text("❌ AI provider недоступний.")
        return

    progress = await query.message.reply_text("⚠️ Шукаю семантичні суперечності між нотатками (AI)…")

    import asyncio
    from vault_writer.ai.synthesizer import check_all_contradictions
    loop = asyncio.get_running_loop()
    try:
        contradictions = await loop.run_in_executor(
            None, check_all_contradictions, index, config.vault.path, provider, 5
        )
    except Exception as exc:
        logger.error("lint_contradictions: %s", exc)
        await progress.delete()
        await query.message.reply_text(f"❌ Помилка: {exc}")
        return

    await progress.delete()

    if not contradictions:
        await query.message.reply_text("✅ Суперечностей між нотатками не знайдено.")
        return

    lines = [f"⚠️ *Знайдено {len(contradictions)} суперечностей:*\n"]
    for c in contradictions[:8]:
        folder = c.get("folder", "?")
        note_a = c.get("note_a", "?")
        note_b = c.get("note_b", "?")
        summary = c.get("summary", "")
        claim_a = c.get("claim_a", "")
        claim_b = c.get("claim_b", "")
        lines.append(f"📁 *{folder}*")
        lines.append(f"  «{note_a}» vs «{note_b}»")
        if claim_a and claim_b:
            lines.append(f"  _{claim_a}_ ↔ _{claim_b}_")
        elif summary:
            lines.append(f"  _{summary}_")
        lines.append("")

    lines.append("💡 Переглянь ці нотатки і виправ або об'єднай суперечливі твердження.")
    await query.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def handle_settings_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Called from message handler when pending_settings_input is set.
    Returns True if the message was consumed.
    """
    key = context.user_data.get("pending_settings_input")
    if not key:
        return False

    context.user_data.pop("pending_settings_input", None)
    text = (update.message.text or "").strip()
    config = context.bot_data["config"]
    from telegram.i18n import t

    # Validate time format
    if key.endswith("_time"):
        import re
        if not re.match(r"^\d{2}:\d{2}$", text):
            await update.message.reply_text("❌ Invalid format. Use HH:MM (e.g. 21:00)")
            return True
        h, m = map(int, text.split(":"))
        if not (0 <= h <= 23 and 0 <= m <= 59):
            await update.message.reply_text("❌ Invalid time. Hours 00–23, minutes 00–59.")
            return True
        # Apply to in-memory config
        new_time = _time(h, m)
        _TIME_ATTRS = {
            "schedule.daily_summary_time":  ("schedule", "daily_summary_time"),
            "schedule.weekly_review_time":  ("schedule", "weekly_review_time"),
            "schedule.monthly_review_time": ("schedule", "monthly_review_time"),
        }
        section, attr = _TIME_ATTRS.get(key, (None, None))
        if section and attr:
            setattr(getattr(config, section), attr, new_time)
        _persist_yaml(config.config_path, _YAML_PATHS[key], text)
        await update.message.reply_text(
            f"✅ Time updated to {text}\n⚠️ Restart bot to reschedule jobs.",
        )
        return True

    # Model name (free text)
    if key == "ai.model":
        if not text:
            await update.message.reply_text("❌ Model name cannot be empty.")
            return True
        config.ai.model = text
        _persist_yaml(config.config_path, _YAML_PATHS[key], text)
        await update.message.reply_text(
            f"✅ Model set to `{text}`\n⚠️ Restart bot to apply.",
            parse_mode="Markdown",
        )
        return True

    return True
