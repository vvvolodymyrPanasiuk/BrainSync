"""Interactive BrainSync installer: generates config.yaml and verifies connections."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


# ── UI helpers ────────────────────────────────────────────────────────────────

def _hr(char: str = "─", width: int = 56) -> None:
    print(char * width)


def _header(title: str) -> None:
    print()
    _hr("═")
    print(f"  {title}")
    _hr("═")
    print()


def _pick(prompt: str, options: list[str], default: int = 1) -> int:
    """Show numbered options, return 1-based index of chosen option."""
    print(f"{prompt}")
    for i, opt in enumerate(options, 1):
        marker = " ◄" if i == default else ""
        print(f"  [{i}] {opt}{marker}")
    while True:
        raw = input(f"\n  Choose [1-{len(options)}] (default {default}): ").strip()
        if not raw:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw)
        print(f"  ❌ Enter a number between 1 and {len(options)}")


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"  {prompt}{suffix}: ").strip()
    return val if val else default


def _ask_bool(prompt: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    val = input(f"  {prompt} {suffix}: ").strip().lower()
    if not val:
        return default
    return val in ("y", "yes")


# ── Main wizard ───────────────────────────────────────────────────────────────

def main() -> None:
    _header("BrainSync Setup Wizard")

    # ── Vault path ────────────────────────────────────────────────────────────
    print("Step 1/6 — Vault location")
    print("  Where is your Obsidian vault? (the folder containing your .md notes)")
    print()
    vault_path = _ask("Vault path", r"C:\SecondaryBrain")
    while not Path(vault_path).is_dir():
        print(f"  ❌ Directory not found: {vault_path}")
        vault_path = _ask("Vault path")
    print(f"  ✓ Found: {vault_path}\n")

    # ── AI provider ───────────────────────────────────────────────────────────
    _hr()
    print("\nStep 2/6 — AI provider\n")
    provider_idx = _pick(
        "Which AI provider do you want to use?",
        [
            "Anthropic (Claude API) — requires an API key, works via internet",
            "Ollama                 — fully local, free, requires Ollama running",
        ],
        default=1,
    )
    ai_provider = "anthropic" if provider_idx == 1 else "ollama"

    api_key = ""
    ollama_url = "http://localhost:11434"
    ollama_vision_model = ""

    if ai_provider == "anthropic":
        print()
        api_key = _ask("Anthropic API key (sk-ant-...)")
        while not api_key.startswith("sk-"):
            print("  ❌ Key should start with sk-ant- or sk-")
            api_key = _ask("Anthropic API key")
        model = "claude-sonnet-4-6"
        print(f"  ✓ Model: {model}\n")
    else:
        print()
        print("  Make sure Ollama is running: https://ollama.com")
        ollama_url = _ask("Ollama URL", "http://localhost:11434")
        print()
        print("  Recommended text models:  mistral, llama3, gemma3, phi4")
        model = _ask("Ollama text model", "mistral")
        print()
        print("  Recommended vision models: llava, moondream  (leave blank to disable)")
        ollama_vision_model = _ask("Ollama vision model (for photos)", "")
        print()

    # ── Processing mode ───────────────────────────────────────────────────────
    _hr()
    print("\nStep 3/6 — Processing mode\n")
    mode_idx = _pick(
        "How much AI processing per note?",
        [
            "minimal  — classification only (fastest, 0–1 AI calls)",
            "balanced — classification + content formatting (recommended, 1–2 calls)",
            "full     — classification + formatting + auto wikilinks (slowest, 2–3 calls)",
        ],
        default=2,
    )
    processing_mode = ["minimal", "balanced", "full"][mode_idx - 1]
    print(f"  ✓ Mode: {processing_mode}\n")

    # ── Telegram ──────────────────────────────────────────────────────────────
    _hr()
    print("\nStep 4/6 — Telegram bot\n")
    print("  Create a bot at https://t.me/BotFather → /newbot → copy the token")
    print("  Get your user ID from https://t.me/userinfobot\n")
    bot_token = _ask("Telegram bot token")
    while not bot_token:
        bot_token = _ask("Telegram bot token (required)")
    user_id_str = _ask("Your Telegram user ID")
    while not user_id_str.isdigit():
        user_id_str = _ask("Telegram user ID (numbers only, e.g. 123456789)")
    print()

    # ── Embedding backend ─────────────────────────────────────────────────────
    _hr()
    print("\nStep 5/6 — Semantic search & RAG embeddings\n")
    embed_idx = _pick(
        "Which embedding backend for semantic search?",
        [
            "sentence-transformers — local model, works offline (recommended)",
            "Ollama                — use Ollama for embeddings too",
        ],
        default=1,
    )
    embed_backend = "sentence-transformers" if embed_idx == 1 else "ollama"
    embed_model = "paraphrase-multilingual-MiniLM-L12-v2"
    if embed_backend == "ollama":
        print()
        print("  Recommended: nomic-embed-text  (run: ollama pull nomic-embed-text)")
        embed_model = _ask("Ollama embedding model", "nomic-embed-text")
    print(f"  ✓ Backend: {embed_backend}  Model: {embed_model}\n")

    # ── Git sync ──────────────────────────────────────────────────────────────
    _hr()
    print("\nStep 6/7 — System message language\n")
    locale_idx = _pick(
        "Bot system messages language:",
        ["English (default)", "Ukrainian"],
    )
    locale = "uk" if locale_idx == 2 else "en"

    print("\nStep 7/7 — Git sync (optional)\n")
    git_enabled = _ask_bool("Auto-commit notes to git?", default=True)
    git_push = False
    if git_enabled:
        git_push = _ask_bool("Also push to remote (GitHub etc.)?", default=False)
    print()

    # ── Write + test ──────────────────────────────────────────────────────────
    _hr()
    print("\nGenerating config.yaml…")
    _write_config(
        vault_path=vault_path,
        bot_token=bot_token,
        user_id=int(user_id_str),
        api_key=api_key,
        ai_provider=ai_provider,
        model=model,
        ollama_url=ollama_url,
        ollama_vision_model=ollama_vision_model,
        processing_mode=processing_mode,
        git_enabled=git_enabled,
        git_push=git_push,
        embed_backend=embed_backend,
        embed_model=embed_model,
        locale=locale,
    )

    print("Copying .brain/ templates…")
    _copy_brain_templates()

    print("Testing Telegram connection…")
    _test_telegram(bot_token, int(user_id_str))

    if api_key:
        print("Testing Anthropic connection…")
        _test_ai(api_key, ai_provider)

    _hr("═")
    print()
    print("  ✅  Setup complete!")
    print()
    print("  Run  start.bat  to launch BrainSync.")
    print()
    _hr("═")
    print()


# ── Config writer ─────────────────────────────────────────────────────────────

def _write_config(**kw) -> None:
    import yaml
    cfg = {
        "locale": kw.get("locale", "en"),
        "ai": {
            "provider": kw["ai_provider"],
            "model": kw["model"],
            "ollama_url": kw["ollama_url"],
            "ollama_vision_model": kw["ollama_vision_model"],
            "processing_mode": kw["processing_mode"],
            "agents_file": ".brain/AGENTS.md",
            "skills_path": ".brain/skills/",
            "inject_vault_index": True,
            "max_context_tokens": 4000,
            "api_key": kw["api_key"],
        },
        "vault": {
            "path": kw["vault_path"],
            "language": "uk",
        },
        "embedding": {
            "backend": kw["embed_backend"],
            "model": kw["embed_model"],
            "ollama_embed_url": kw.get("ollama_url", "http://localhost:11434"),
            "index_path": "data/chroma",
            "similarity_duplicate_threshold": 0.85,
            "similarity_related_threshold": 0.70,
            "top_k_results": 5,
        },
        "media": {
            "max_voice_duration_seconds": 300,
            "transcription_model": "small",
            "pdf_max_pages": 50,
            "pdf_ai_context_chars": 3000,
            "max_file_size_mb": 20,
        },
        "enrichment": {
            "add_wikilinks": True,
            "update_moc": True,
            "max_related_notes": 5,
            "scan_vault_on_start": True,
        },
        "telegram": {
            "bot_token": kw["bot_token"],
            "allowed_user_ids": [kw["user_id"]],
        },
        "prefixes": {
            "note": ["нотатка:", "note:"],
            "task": ["задача:", "task:", "todo:"],
            "idea": ["ідея:", "idea:"],
            "journal": ["день:", "journal:"],
        },
        "git": {
            "enabled": kw["git_enabled"],
            "auto_commit": kw["git_enabled"],
            "commit_message": "vault: auto-save {date} {time}",
            "push_remote": kw["git_push"],
            "remote": "origin",
            "branch": "main",
            "push_interval_minutes": 30,
        },
        "schedule": {
            "daily_summary": {"enabled": True, "time": "21:00"},
            "weekly_review": {"enabled": True, "day": "sunday", "time": "20:00"},
            "monthly_review": {"enabled": True, "day": 1, "time": "10:00"},
        },
        "logging": {
            "level": "info",
            "log_to_file": True,
            "log_path": "logs/vault.log",
            "log_ai_decisions": True,
        },
    }
    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print("  ✓ config.yaml written")


def _copy_brain_templates() -> None:
    brain_src = Path(__file__).parent / ".brain"
    brain_dst = Path(".brain")
    if not brain_dst.exists():
        shutil.copytree(brain_src, brain_dst)
        print("  ✓ .brain/ templates copied")
    else:
        print("  ℹ .brain/ already exists — skipping")


def _test_telegram(bot_token: str, user_id: int) -> None:
    try:
        import asyncio
        from telegram import Bot
        async def _send():
            bot = Bot(token=bot_token)
            await bot.send_message(chat_id=user_id, text="BrainSync setup complete ✓")
        asyncio.run(_send())
        print("  ✓ Telegram connection OK")
    except Exception as exc:
        print(f"  ⚠  Telegram test failed: {exc}")


def _test_ai(api_key: str, provider: str) -> None:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=5,
            messages=[{"role": "user", "content": "ping"}],
        )
        print("  ✓ Anthropic connection OK")
    except Exception as exc:
        print(f"  ⚠  Anthropic test failed: {exc}")


if __name__ == "__main__":
    main()
