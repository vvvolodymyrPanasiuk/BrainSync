"""Config loader: parse config.yaml into AppConfig dataclasses, validate fields."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    pass


# ── Enums (imported from their canonical locations after those modules exist) ──
# ProcessingMode is defined in vault_writer/ai/provider.py
# NoteType is defined in vault_writer/vault/writer.py
# We import them lazily to avoid circular imports.


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class AIConfig:
    provider: str
    model: str
    ollama_url: str
    processing_mode: str           # raw string; cast to ProcessingMode by caller
    agents_file: str
    skills_path: str
    inject_vault_index: bool
    max_context_tokens: int
    api_key: str                   # NEVER logged or committed
    ollama_vision_model: str = ""  # vision model for Ollama (e.g. "llava")


@dataclass
class VaultConfig:
    path: str
    language: str


@dataclass
class TelegramConfig:
    bot_token: str                 # NEVER logged or committed
    allowed_user_ids: list[int]


@dataclass
class GitConfig:
    enabled: bool
    auto_commit: bool
    commit_message: str
    push_remote: bool
    remote: str
    branch: str
    push_interval_minutes: int


@dataclass
class ScheduleConfig:
    daily_summary_enabled: bool
    daily_summary_time: time
    weekly_review_enabled: bool
    weekly_review_day: str
    weekly_review_time: time
    monthly_review_enabled: bool
    monthly_review_day: int
    monthly_review_time: time


@dataclass
class MediaConfig:
    max_voice_duration_seconds: int = 300
    transcription_model: str = "small"
    pdf_max_pages: int = 50
    pdf_ai_context_chars: int = 3000
    max_file_size_mb: int = 20


@dataclass
class AppConfig:
    ai: AIConfig
    vault: VaultConfig
    telegram: TelegramConfig
    git: GitConfig
    schedule: ScheduleConfig
    enrichment_add_wikilinks: bool
    enrichment_update_moc: bool
    enrichment_max_related_notes: int
    enrichment_scan_vault_on_start: bool
    logging_level: str
    logging_log_ai_decisions: bool
    logging_log_path: str
    config_path: str               # absolute path to config.yaml (for hot-write)
    media: MediaConfig = field(default_factory=MediaConfig)
    prefixes: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class SessionStats:
    tokens_consumed: int = 0
    last_note_path: str = ""
    notes_saved_today: int = 0
    vault_notes_total: int = 0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_time(value: str, field_name: str) -> time:
    if not re.match(r"^\d{2}:\d{2}$", str(value)):
        raise ValueError(f"{field_name}: must be HH:MM format, got: {value!r}")
    h, m = value.split(":")
    return time(int(h), int(m))


# ── Main loader ───────────────────────────────────────────────────────────────

def load_config(config_path: str) -> AppConfig:
    """Parse config.yaml and validate all fields. Raises ValueError on violations."""
    path = Path(config_path)
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    ai_raw = raw.get("ai", {})
    vault_raw = raw.get("vault", {})
    telegram_raw = raw.get("telegram", {})
    git_raw = raw.get("git", {})
    schedule_raw = raw.get("schedule", {})
    enrichment_raw = raw.get("enrichment", {})
    logging_raw = raw.get("logging", {})
    prefixes_raw = raw.get("prefixes", {})
    media_raw = raw.get("media", {})

    # ── Validation ────────────────────────────────────────────────────────────
    errors: list[str] = []

    provider = ai_raw.get("provider", "")
    if provider not in ("anthropic", "ollama"):
        errors.append(f"ai.provider must be 'anthropic' or 'ollama', got: {provider!r}")

    mode = ai_raw.get("processing_mode", "")
    if mode not in ("minimal", "balanced", "full"):
        errors.append(f"ai.processing_mode must be 'minimal'|'balanced'|'full', got: {mode!r}")

    api_key = ai_raw.get("api_key", "")
    if provider == "anthropic" and not api_key:
        errors.append("ai.api_key must not be empty when provider='anthropic'")

    vault_path = vault_raw.get("path", "")
    if vault_path and not Path(vault_path).is_dir():
        errors.append(f"vault.path does not exist as a directory: {vault_path!r}")

    bot_token = telegram_raw.get("bot_token", "")
    if not bot_token:
        errors.append("telegram.bot_token must not be empty")

    allowed_ids = telegram_raw.get("allowed_user_ids", [])
    if not allowed_ids:
        logging.warning("telegram.allowed_user_ids is empty — bot will refuse all messages")

    monthly_day = schedule_raw.get("monthly_review", {}).get("day", 1)
    if not (1 <= int(monthly_day) <= 28):
        errors.append(f"schedule.monthly_review.day must be 1–28, got: {monthly_day}")

    if errors:
        raise ValueError("config.yaml validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

    # ── Schedule parsing ──────────────────────────────────────────────────────
    daily_raw = schedule_raw.get("daily_summary", {})
    weekly_raw = schedule_raw.get("weekly_review", {})
    monthly_raw = schedule_raw.get("monthly_review", {})

    schedule = ScheduleConfig(
        daily_summary_enabled=daily_raw.get("enabled", True),
        daily_summary_time=_parse_time(daily_raw.get("time", "21:00"), "schedule.daily_summary.time"),
        weekly_review_enabled=weekly_raw.get("enabled", True),
        weekly_review_day=weekly_raw.get("day", "sunday"),
        weekly_review_time=_parse_time(weekly_raw.get("time", "20:00"), "schedule.weekly_review.time"),
        monthly_review_enabled=monthly_raw.get("enabled", True),
        monthly_review_day=int(monthly_day),
        monthly_review_time=_parse_time(monthly_raw.get("time", "10:00"), "schedule.monthly_review.time"),
    )

    return AppConfig(
        ai=AIConfig(
            provider=provider,
            model=ai_raw.get("model", "claude-sonnet-4-6"),
            ollama_url=ai_raw.get("ollama_url", "http://localhost:11434"),
            processing_mode=mode,
            agents_file=ai_raw.get("agents_file", ".brain/AGENTS.md"),
            skills_path=ai_raw.get("skills_path", ".brain/skills/"),
            inject_vault_index=ai_raw.get("inject_vault_index", True),
            max_context_tokens=ai_raw.get("max_context_tokens", 4000),
            api_key=api_key,
            ollama_vision_model=ai_raw.get("ollama_vision_model", ""),
        ),
        vault=VaultConfig(
            path=vault_path,
            language=vault_raw.get("language", "uk"),
        ),
        telegram=TelegramConfig(
            bot_token=bot_token,
            allowed_user_ids=[int(uid) for uid in (allowed_ids or [])],
        ),
        git=GitConfig(
            enabled=git_raw.get("enabled", True),
            auto_commit=git_raw.get("auto_commit", True),
            commit_message=git_raw.get("commit_message", "vault: auto-save {date} {time}"),
            push_remote=git_raw.get("push_remote", True),
            remote=git_raw.get("remote", "origin"),
            branch=git_raw.get("branch", "main"),
            push_interval_minutes=git_raw.get("push_interval_minutes", 30),
        ),
        schedule=schedule,
        enrichment_add_wikilinks=enrichment_raw.get("add_wikilinks", True),
        enrichment_update_moc=enrichment_raw.get("update_moc", True),
        enrichment_max_related_notes=enrichment_raw.get("max_related_notes", 5),
        enrichment_scan_vault_on_start=enrichment_raw.get("scan_vault_on_start", True),
        logging_level=logging_raw.get("level", "info"),
        logging_log_ai_decisions=logging_raw.get("log_ai_decisions", True),
        logging_log_path=logging_raw.get("log_path", "logs/vault.log"),
        config_path=str(path.resolve()),
        media=MediaConfig(
            max_voice_duration_seconds=int(media_raw.get("max_voice_duration_seconds", 300)),
            transcription_model=str(media_raw.get("transcription_model", "small")),
            pdf_max_pages=int(media_raw.get("pdf_max_pages", 50)),
            pdf_ai_context_chars=int(media_raw.get("pdf_ai_context_chars", 3000)),
            max_file_size_mb=int(media_raw.get("max_file_size_mb", 20)),
        ),
        prefixes=prefixes_raw or {
            "note": ["нотатка:", "note:"],
            "task": ["задача:", "task:", "todo:"],
            "idea": ["ідея:", "idea:"],
            "journal": ["день:", "journal:"],
        },
    )


def setup_logging(config: AppConfig) -> None:
    """Configure file + console logging. Never logs api_key or bot_token."""
    level = getattr(logging, config.logging_level.upper(), logging.INFO)
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if config.logging_log_path:
        log_path = Path(config.logging_log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )


def get_ai_provider(config: AppConfig):
    """Return AIProvider instance based on config. Raises for unsupported providers."""
    from vault_writer.ai.anthropic_provider import AnthropicProvider
    from vault_writer.ai.ollama_provider import OllamaProvider

    if config.ai.provider == "anthropic":
        return AnthropicProvider(api_key=config.ai.api_key, model=config.ai.model)
    if config.ai.provider == "ollama":
        return OllamaProvider(
            base_url=config.ai.ollama_url,
            model=config.ai.model,
            vision_model=config.ai.ollama_vision_model,
        )
    raise ValueError(f"Unsupported AI provider: {config.ai.provider!r}")


def update_processing_mode(config_path: str, mode: str) -> None:
    """Safely rewrite config.yaml updating only ai.processing_mode. Preserves all other fields."""
    path = Path(config_path)
    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg.setdefault("ai", {})["processing_mode"] = mode
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
