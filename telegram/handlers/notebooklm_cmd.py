"""NotebookLM command handler — /notebooklm <request>

Routing:
  /notebooklm                          → help text
  /notebooklm <youtube url>            → YouTube Q&A session (youtube_chat flow)
  /notebooklm <generation request>     → vault search + generate artifact via CLI
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import sys
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

_YOUTUBE_RE = re.compile(
    r"https?://(www\.)?(youtube\.com/watch|youtu\.be/)\S+", re.IGNORECASE
)

# Maps generation type → triggering keywords (lowercase)
_GEN_MAP: dict[str, list[str]] = {
    "slide-deck":   ["презентац", "слайди", "slide", "pptx", "powerpoint"],
    "audio":        ["подкаст", "podcast", "аудіо", "audio overview"],
    "infographic":  ["інфографік", "infographic"],
    "mind-map":     ["mind map", "mindmap", "майнд мап", "карту знань", "карта знань"],
    "quiz":         ["квіз", "quiz", "тест", "вікторин"],
    "flashcards":   ["флешкарт", "flashcard", "картк"],
    "report":       ["звіт", "report", "аналіз", "briefing", "study guide", "огляд"],
}

_GEN_EXT: dict[str, str] = {
    "slide-deck": ".pdf",
    "audio":      ".mp3",
    "infographic":".png",
    "mind-map":   ".json",
    "quiz":       ".md",
    "flashcards": ".md",
    "report":     ".md",
}

_HELP_TEXT = (
    "*NotebookLM — використання:*\n\n"
    "🎬 *YouTube відео:*\n"
    "`/notebooklm https://youtube.com/watch?v=...`\n"
    "→ Завантажує відео, задавай питання по ньому і зберігай у vault.\n\n"
    "📊 *Генерація з нотаток vault:*\n"
    "`/notebooklm зроби презентацію по нотатках про CQRS`\n"
    "`/notebooklm подкаст по темі Python async`\n"
    "`/notebooklm інфографіка по архітектурі мікросервісів`\n"
    "`/notebooklm mind map по Docker`\n"
    "`/notebooklm квіз по базах даних`\n"
    "`/notebooklm звіт по Event Sourcing`\n\n"
    "*Доступні типи:* презентація, подкаст, інфографіка, mind map, квіз, флешкарти, звіт\n\n"
    "⚠️ Потребує: `notebooklm-py` встановленого і Google-акаунт авторизованого."
)

_NOT_INSTALLED = (
    "❌ `notebooklm-py` не встановлено.\n\n"
    "Встанови у звичайному терміналі:\n"
    "```\npip install \"notebooklm-py[browser]\"\nplaywright install chromium\n"
    "notebooklm login\n```"
)

_NOT_AUTHENTICATED = (
    "❌ NotebookLM не авторизований.\n\n"
    "Запусти у терміналі:\n```\nnotebooklm login\n```\n"
    "та залогінься у Google-акаунт у браузері що відкриється."
)


def _nlm_bin() -> str | None:
    """Return path to notebooklm CLI, or None if not found."""
    if p := shutil.which("notebooklm"):
        return p
    home = Path.home()
    candidate = (
        home / ".notebooklm-venv" / "Scripts" / "notebooklm.exe"
        if sys.platform == "win32"
        else home / ".notebooklm-venv" / "bin" / "notebooklm"
    )
    return str(candidate) if candidate.exists() else None


async def _nlm(*args: str, timeout: int = 120) -> tuple[int, str, str]:
    """Run a notebooklm CLI command. Returns (returncode, stdout, stderr)."""
    bin_path = _nlm_bin()
    if not bin_path:
        return 1, "", "notebooklm CLI not found"
    proc = await asyncio.create_subprocess_exec(
        bin_path, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode, stdout.decode(errors="replace").strip(), stderr.decode(errors="replace").strip()
    except asyncio.TimeoutError:
        proc.kill()
        return 1, "", f"Timeout after {timeout}s"


def _detect_gen_type(text: str) -> str | None:
    lower = text.lower()
    for gen_type, keywords in _GEN_MAP.items():
        if any(kw in lower for kw in keywords):
            return gen_type
    return None


def _parse_id(stdout: str, *keys: str) -> str | None:
    """Try to extract an ID from CLI JSON output."""
    try:
        data = json.loads(stdout)
        for key in keys:
            if val := data.get(key):
                return str(val)
        # sometimes nested: {"notebook": {"id": "..."}}
        for v in data.values():
            if isinstance(v, dict):
                for key in keys:
                    if val := v.get(key):
                        return str(val)
    except Exception:
        pass
    return None


def _auth_file_exists() -> bool:
    return (Path.home() / ".notebooklm" / "storage_state.json").exists()


# ── Main handler ──────────────────────────────────────────────────────────────

async def cmd_notebooklm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from telegram.handlers.commands import auth_check
    config = context.bot_data["config"]
    if not auth_check(update, config):
        return

    request = " ".join(context.args).strip() if context.args else ""

    if not request:
        await update.message.reply_text(_HELP_TEXT, parse_mode="Markdown")
        return

    if not _nlm_bin():
        await update.message.reply_text(_NOT_INSTALLED, parse_mode="Markdown")
        return

    if not _auth_file_exists():
        await update.message.reply_text(_NOT_AUTHENTICATED, parse_mode="Markdown")
        return

    # Route: YouTube URL
    if _YOUTUBE_RE.search(request):
        url = _YOUTUBE_RE.search(request).group(0)
        from telegram.handlers.youtube_chat import start_session
        await start_session(update, context, url)
        return

    # Route: generation request
    gen_type = _detect_gen_type(request)
    if gen_type:
        await _generate_from_vault(update, context, request, gen_type)
        return

    # Fallback: no recognized pattern
    await update.message.reply_text(
        "Не зрозумів що треба зробити. Вкажи тип: презентація, подкаст, інфографіка, mind map, квіз або youtube-посилання.\n\n"
        "/notebooklm — показати довідку.",
        parse_mode="Markdown",
    )


# ── Generation flow ───────────────────────────────────────────────────────────

async def _generate_from_vault(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    request: str,
    gen_type: str,
) -> None:
    config       = context.bot_data["config"]
    vector_store = context.bot_data.get("vector_store")

    if vector_store is None or not vector_store.is_ready():
        await update.message.reply_text("❌ Vector index не готовий. Спробуй `/reindex`.")
        return

    # 1. Find relevant vault notes
    results = vector_store.hybrid_search(request, top_k=5)
    if not results:
        await update.message.reply_text("❌ Не знайдено релевантних нотаток у vault по цьому запиту.")
        return

    vault_root = Path(config.vault.path)
    note_paths = [str(vault_root / r.file_path) for r in results if (vault_root / r.file_path).exists()]
    if not note_paths:
        await update.message.reply_text("❌ Нотатки знайдено в індексі, але файли не існують. Спробуй `/reindex`.")
        return

    progress = await update.message.reply_text(
        f"🔍 Знайдено {len(note_paths)} нотаток. Створюю NotebookLM notebook…"
    )

    nb_id: str | None = None
    try:
        # 2. Create notebook
        rc, stdout, stderr = await _nlm("create", f"BrainSync: {request[:60]}", "--json")
        if rc != 0 or not stdout:
            await progress.edit_text(f"❌ Помилка створення notebook: `{stderr[:300]}`", parse_mode="Markdown")
            return
        nb_id = _parse_id(stdout, "id", "notebook_id")
        if not nb_id:
            await progress.edit_text(f"❌ Не вдалось отримати ID notebook.\nOutput: `{stdout[:200]}`", parse_mode="Markdown")
            return

        # 3. Set context
        await _nlm("use", nb_id)

        # 4. Add vault notes as sources
        await progress.edit_text(f"📚 Завантажую {len(note_paths)} нотаток у NotebookLM…")
        for path in note_paths:
            rc, _, err = await _nlm("source", "add", path, timeout=30)
            if rc != 0:
                logger.warning("notebooklm source add failed for %s: %s", path, err)

        # 5. Wait for sources to process
        await progress.edit_text("⚙️ NotebookLM обробляє нотатки…")
        await _nlm("source", "wait", timeout=180)

        # 6. Generate artifact
        gen_type_label = {
            "slide-deck": "презентацію", "audio": "подкаст",
            "infographic": "інфографіку", "mind-map": "mind map",
            "quiz": "квіз", "flashcards": "флешкарти", "report": "звіт",
        }.get(gen_type, gen_type)
        await progress.edit_text(f"🎨 Генерую {gen_type_label}… (може зайняти кілька хвилин)")

        rc, stdout, stderr = await _nlm("generate", gen_type, "--json", timeout=60)
        if rc != 0:
            await progress.edit_text(f"❌ Помилка генерації: `{stderr[:300]}`", parse_mode="Markdown")
            return
        artifact_id = _parse_id(stdout, "id", "artifact_id")

        # 7. Wait for artifact completion
        await progress.edit_text(f"⏳ Чекаю на завершення генерації {gen_type_label}…")
        wait_args = ["artifact", "wait"]
        if artifact_id:
            wait_args.append(artifact_id)
        # podcasts can take up to 20 min, others usually 2-5 min
        wait_timeout = 1200 if gen_type == "audio" else 600
        await _nlm(*wait_args, timeout=wait_timeout)

        # 8. Download and send
        await progress.edit_text("📥 Завантажую результат…")
        ext = _GEN_EXT[gen_type]
        with tempfile.TemporaryDirectory() as tmpdir:
            outfile = Path(tmpdir) / f"brainsync_{gen_type}{ext}"
            rc, _, stderr = await _nlm("download", gen_type, str(outfile), timeout=60)
            if rc != 0 or not outfile.exists():
                await progress.edit_text(f"❌ Помилка завантаження файлу: `{stderr[:300]}`", parse_mode="Markdown")
                return

            await progress.delete()
            caption = f"✅ {gen_type_label.capitalize()} по запиту:\n_{request[:120]}_"
            with open(outfile, "rb") as fh:
                if ext == ".mp3":
                    await update.message.reply_audio(fh, filename=outfile.name, caption=caption, parse_mode="Markdown")
                elif ext == ".png":
                    await update.message.reply_photo(fh, caption=caption, parse_mode="Markdown")
                else:
                    await update.message.reply_document(fh, filename=outfile.name, caption=caption, parse_mode="Markdown")

    except Exception as exc:
        logger.error("notebooklm_cmd: generation failed: %s", exc)
        try:
            await progress.edit_text(f"❌ Несподівана помилка: `{exc}`", parse_mode="Markdown")
        except Exception:
            pass

    finally:
        if nb_id:
            await _nlm("delete", nb_id, timeout=30)
            logger.debug("notebooklm_cmd: deleted notebook %s", nb_id)
