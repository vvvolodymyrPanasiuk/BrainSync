"""Conversation context manager — rolling message history with AI compaction.

Stores recent turns in PTB user_data so the router has conversational context:
  - "збережи це" → knows what "це" refers to
  - "додай до попередньої нотатки" → knows which note
  - Follow-up questions stay coherent

Auto-compacts when history exceeds MAX_CHARS (AI summarizes → summary replaces turns).
Topic shift detected when general_category changes for 2+ consecutive turns → soft compact.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_KEY = "conv_ctx"          # key in PTB user_data
MAX_CHARS  = 5_000         # compact when total history chars exceed this
MAX_TURNS  = 14            # hard cap: drop oldest turns beyond this
SAVE_REPLY = 80            # max chars of assistant reply stored in history


# ── Public API ────────────────────────────────────────────────────────────────

def get_ctx(user_data: dict) -> dict:
    """Return (or initialise) conversation context dict from user_data."""
    if _KEY not in user_data:
        user_data[_KEY] = {"turns": [], "summary": ""}
    return user_data[_KEY]


def add_user_turn(user_data: dict, message: str, intent: str = "", folder: str = "") -> None:
    """Append a user message to the conversation history."""
    ctx = get_ctx(user_data)
    ctx["turns"].append({
        "role":   "user",
        "text":   message[:600],   # cap individual turn length
        "intent": intent,
        "folder": folder,
    })
    _trim(ctx)


def add_assistant_turn(user_data: dict, reply: str, intent: str = "", folder: str = "") -> None:
    """Append the bot reply to the conversation history."""
    ctx = get_ctx(user_data)
    ctx["turns"].append({
        "role":   "assistant",
        "text":   reply[:SAVE_REPLY],
        "intent": intent,
        "folder": folder,
    })
    _trim(ctx)


def needs_compaction(user_data: dict) -> bool:
    """True when history is large enough to warrant compaction."""
    ctx = get_ctx(user_data)
    total = sum(len(t["text"]) for t in ctx["turns"]) + len(ctx.get("summary", ""))
    return total > MAX_CHARS


def detect_topic_shift(user_data: dict, new_folder: str) -> bool:
    """True when the last 2 assistant turns all differ from new_folder (top-level folder).

    Signals the user has switched to a completely different domain.
    Only triggers when there are at least 4 turns so we don't compact prematurely.
    """
    ctx = get_ctx(user_data)
    turns = ctx["turns"]
    if len(turns) < 4 or not new_folder:
        return False

    new_top = new_folder.split("/")[0].lower()
    # Collect top-level folders from last 2 assistant turns
    recent_tops = [
        t["folder"].split("/")[0].lower()
        for t in turns[-4:]
        if t["role"] == "assistant" and t.get("folder")
    ]
    if len(recent_tops) < 2:
        return False

    # Topic shift = new folder differs from ALL recent assistant turns
    return new_top not in recent_tops and len(set(recent_tops)) == 1


def compact(user_data: dict, provider) -> str:
    """Summarise conversation history via AI and replace turns with compact summary.

    Returns the generated summary string (empty string on failure).
    """
    ctx = get_ctx(user_data)
    turns = ctx.get("turns", [])
    if not turns:
        return ""

    history_text = _render_for_prompt(ctx, include_summary=True)
    prompt = (
        "Summarise this conversation in 4-6 bullet points. "
        "Capture: topics discussed, notes saved (titles + folders), decisions made, open questions. "
        "Be concrete and brief — this summary will replace the full history.\n\n"
        f"{history_text}\n\nSummary (bullet points):"
    )
    try:
        summary = provider.complete(prompt, max_tokens=400)
        summary = re.sub(r"<think>.*?</think>", "", summary, flags=re.DOTALL).strip()
    except Exception as exc:
        logger.warning("context_manager: compact AI call failed: %s", exc)
        # Fallback: plain concatenation of last 3 turns
        summary = " | ".join(t["text"][:60] for t in turns[-3:])

    ctx["turns"] = []
    ctx["summary"] = summary[:800]
    logger.info("context_manager: compacted history → %d chars summary", len(ctx["summary"]))
    return ctx["summary"]


def clear(user_data: dict) -> None:
    """Hard reset — wipe history and summary."""
    user_data[_KEY] = {"turns": [], "summary": ""}


def to_prompt_block(user_data: dict) -> str:
    """Return a formatted history block to inject into the router prompt.

    Returns empty string when there is no useful history.
    """
    ctx = get_ctx(user_data)
    if not ctx["turns"] and not ctx.get("summary"):
        return ""
    return _render_for_prompt(ctx, include_summary=True)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _trim(ctx: dict) -> None:
    """Keep turns within MAX_TURNS hard cap."""
    if len(ctx["turns"]) > MAX_TURNS:
        ctx["turns"] = ctx["turns"][-MAX_TURNS:]


def _render_for_prompt(ctx: dict, include_summary: bool = True) -> str:
    lines: list[str] = []

    if include_summary and ctx.get("summary"):
        lines.append(f"[Previous context — compacted]\n{ctx['summary']}\n")

    for t in ctx["turns"]:
        if t["role"] == "user":
            lines.append(f"User: {t['text']}")
        else:
            meta = ""
            if t.get("intent"):
                meta = f" [{t['intent']}"
                if t.get("folder"):
                    meta += f" → {t['folder']}"
                meta += "]"
            lines.append(f"Assistant{meta}: {t['text']}")

    return "\n".join(lines)
