"""Interactive BrainSync installer: generates config.yaml and verifies connections."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"{prompt}{suffix}: ").strip()
    return val if val else default


def ask_bool(prompt: str, default: bool = True) -> bool:
    default_str = "Y/n" if default else "y/N"
    val = input(f"{prompt} [{default_str}]: ").strip().lower()
    if not val:
        return default
    return val in ("y", "yes")


def main() -> None:
    print("\n🧠 BrainSync Setup\n")

    vault_path = ask("Vault path (Obsidian folder)", r"C:\SecondaryBrain")
    while not Path(vault_path).is_dir():
        print(f"  ❌ Path not found: {vault_path}")
        vault_path = ask("Vault path (Obsidian folder)")

    bot_token = ask("Telegram bot token")
    while not bot_token:
        bot_token = ask("Telegram bot token (required)")

    user_id_str = ask("Your Telegram user ID (integer)")
    while not user_id_str.isdigit():
        user_id_str = ask("Your Telegram user ID (integer, e.g. 123456789)")

    ai_provider = ask("AI provider", "anthropic").lower()
    api_key = ""
    if ai_provider == "anthropic":
        api_key = ask("Anthropic API key")

    processing_mode = ask("Processing mode (minimal/balanced/full)", "balanced").lower()
    if processing_mode not in ("minimal", "balanced", "full"):
        processing_mode = "balanced"

    git_enabled = ask_bool("Enable git sync?", default=True)
    git_remote = ""
    if git_enabled:
        git_remote = ask("Git remote URL (leave blank to skip push)", "")

    print("\nGenerating config.yaml...")
    _write_config(
        vault_path=vault_path,
        bot_token=bot_token,
        user_id=int(user_id_str),
        api_key=api_key,
        ai_provider=ai_provider,
        processing_mode=processing_mode,
        git_enabled=git_enabled,
        git_remote=git_remote,
    )

    print("Copying .brain/ templates...")
    _copy_brain_templates()

    print("Testing Telegram connection...")
    _test_telegram(bot_token, int(user_id_str))

    if api_key:
        print("Testing AI provider connection...")
        _test_ai(api_key, ai_provider)

    print("\n✅ Setup complete!")
    print("Start the bot with:  start.bat  (Windows) or  bash start.sh  (Unix)\n")


def _write_config(**kw) -> None:
    import yaml
    cfg = {
        "ai": {
            "provider": kw["ai_provider"],
            "model": "claude-sonnet-4-6",
            "ollama_url": "http://localhost:11434",
            "processing_mode": kw["processing_mode"],
            "agents_file": ".brain/AGENTS.md",
            "skills_path": ".brain/skills/",
            "inject_vault_index": True,
            "max_context_tokens": 4000,
            "api_key": kw["api_key"],
        },
        "vault": {"path": kw["vault_path"], "language": "uk"},
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
            "auto_commit": True,
            "commit_message": "vault: auto-save {date} {time}",
            "push_remote": bool(kw["git_remote"]),
            "remote": "origin",
            "branch": "main",
            "push_interval_minutes": 30,
        },
        "schedule": {
            "daily_summary": {"enabled": True, "time": "21:00"},
            "weekly_review": {"enabled": True, "day": "sunday", "time": "20:00"},
            "monthly_review": {"enabled": True, "day": 1, "time": "10:00"},
        },
        "claude_code": {
            "enabled": False,
            "capture_trigger": "manual",
            "save_raw": True,
            "max_session_tokens": 2000,
            "allowed_projects": [],
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
        print("  ℹ .brain/ already exists — skipping copy")


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
        print(f"  ⚠️  Telegram test failed: {exc}")


def _test_ai(api_key: str, provider: str) -> None:
    try:
        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=5,
                messages=[{"role": "user", "content": "ping"}],
            )
        print("  ✓ AI provider connection OK")
    except Exception as exc:
        print(f"  ⚠️  AI test failed: {exc}")


if __name__ == "__main__":
    main()
