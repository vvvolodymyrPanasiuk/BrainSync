"""AI Semantic Router: single-pass AI analysis returning full ActionPlan JSON."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class Intent(str, Enum):
    CREATE_NOTE           = "create_note"
    APPEND_NOTE           = "append_note"
    UPDATE_NOTE           = "update_note"
    MOVE_NOTE             = "move_note"
    SEARCH_VAULT          = "search_vault"
    ANSWER_FROM_VAULT     = "answer_from_vault"
    ANALYZE_VAULT         = "analyze_vault"
    SUMMARIZE_VAULT       = "summarize_vault"
    SEARCH_WEB            = "search_web"
    EXTRACT_STRUCTURED    = "extract_structured_data"
    TRANSCRIBE_AUDIO      = "transcribe_audio"
    OCR_IMAGE             = "ocr_image"
    PARSE_DOCUMENT        = "parse_document"
    REQUEST_CLARIFICATION = "request_clarification"
    CHAT_ONLY             = "chat_only"
    IGNORE_SPAM           = "ignore_spam"
    MANUAL_REVIEW         = "manual_review"


# Intents that should NOT produce a new note
_NO_SAVE_INTENTS = {
    Intent.SEARCH_VAULT,
    Intent.ANSWER_FROM_VAULT,
    Intent.ANALYZE_VAULT,
    Intent.SUMMARIZE_VAULT,
    Intent.SEARCH_WEB,
    Intent.REQUEST_CLARIFICATION,
    Intent.CHAT_ONLY,
    Intent.IGNORE_SPAM,
    Intent.MANUAL_REVIEW,
    Intent.TRANSCRIBE_AUDIO,
    Intent.OCR_IMAGE,
    Intent.MOVE_NOTE,
}


@dataclass
class ActionPlan:
    intent: Intent
    confidence: float
    should_save: bool
    needs_web: bool
    needs_clarification: bool
    note_type: str              # note | task | idea | journal
    general_category: str       # top-level category (Навчання, Бізнес, Особисте, etc.)
    target_folder: str          # specific topic within category
    target_subfolder: str       # narrower subtopic (or "")
    section: str                # optional 4th-level section (or "")
    topic: str
    tags: list[str]
    summary: str
    actions: list[str]
    sources: list[str]
    reason: str
    title: str = ""
    content: str = ""           # pre-formatted note body for save intents (or "")


_ROUTER_SYSTEM = """\
You are the intent routing component of BrainSync — a personal Telegram→Obsidian AI assistant.

VAULT LOCALE: {locale}
All note content (titles, section headers, body text, and your replies to the user) must be
written in this locale. Apply it consistently regardless of what language the user writes in.

Analyze the user message and return ONLY a JSON object with this exact structure:

{
  "intent": "<one of the allowed intents>",
  "confidence": <0.0-1.0>,
  "should_save": <true|false>,
  "needs_web": <true|false>,
  "needs_clarification": <true|false>,
  "note_type": "<note|task|idea|journal>",
  "general_category": "<high-level life area in vault locale>",
  "target_folder": "<specific topic within category in vault locale>",
  "target_subfolder": "<narrower subtopic in vault locale, or empty string>",
  "section": "<deepest optional section in vault locale, or empty string>",
  "topic": "<topic in 1-3 words>",
  "tags": ["<tag1>", "<tag2>"],
  "summary": "<1 sentence summary>",
  "actions": ["<primary_action>"],
  "sources": [],
  "reason": "<1 sentence explanation>",
  "title": "<short note title in vault locale if saving, else empty string>",
  "content": "<formatted Obsidian markdown body in vault locale if should_save=true, else empty string>"
}

ALLOWED INTENTS:
- create_note: User shares a new thought, idea, task, learning, insight, journal entry or content worth saving. should_save=true.
- append_note: User wants to add content to an existing note. should_save=true.
- update_note: User wants to correct/update an existing note. should_save=true.
- search_vault: User wants to find/list/browse notes (e.g. "find notes about X", "do I have anything on Y?"). should_save=false.
- answer_from_vault: User asks about their own notes/thoughts (e.g. "what did I write about X?", "what was my opinion on Y?"). should_save=false.
- analyze_vault: User wants broad vault analysis (e.g. "what do I have?", "analyze my notes", "what topics?"). should_save=false.
- summarize_vault: User wants a summary of recent or topic notes. should_save=false.
- search_web: User explicitly needs external information. Use only if vault clearly cannot satisfy. should_save=false.
- extract_structured_data: User provides structured data (table, receipt, CSV) to parse. should_save=true.
- move_note: User wants to move/relocate an existing note to a different folder. target_folder=DESTINATION folder. should_save=false.
- request_clarification: Message is too ambiguous to route. should_save=false.
- chat_only: Casual talk, greeting, thanks, test, general AI question NOT about vault content. should_save=false.
- ignore_spam: Random characters, obvious spam, noise. should_save=false.
- manual_review: Sensitive/medical/legal content. should_save=false.

FOLDER PATH STRUCTURE (notes stored as: general_category/target_folder[/target_subfolder][/section]/_data/note.md):
- general_category: broad life domain — e.g. "Learning", "Business", "Personal", "Projects", "Health", "Finance", "Creative"
- target_folder: specific topic within category — e.g. "Programming", "Trading", "Cooking", "Sports"
- target_subfolder: narrower sub-area — e.g. "Python", "Indicators", "Boxing" — use only when clearly applicable, else ""
- section: even narrower level — e.g. "Algorithms", "Basics" — use ONLY when strongly needed, else ""
Minimum depth: 2 levels (general_category + target_folder). Maximum: 4 levels.
Folder names must be written in the VAULT LOCALE defined above.

CURRENT VAULT FOLDER STRUCTURE:
{structure_hint}

CONTENT FIELD RULES (for should_save=true intents):
- "content" must be a well-formatted Obsidian markdown note body (NO frontmatter)
- Use three sections with headers translated to VAULT LOCALE: Description, Conclusions, Links
- Fill in the sections meaningfully based on the user's message
- For non-save intents, "content" must be ""

CRITICAL RULES:
1. NOT every message should be saved. Only create_note/append_note/update_note/extract_structured_data → should_save=true.
2. Requests to list/browse/search vault contents → analyze_vault or search_vault, should_save=false.
3. Questions about what user thought/wrote → answer_from_vault, should_save=false.
4. Greetings, thanks, "ok", "test", "don't save" → chat_only, should_save=false.
5. Short questions ending in "?" about external knowledge (not vault) → chat_only.
6. "Don't save this", "just a question", "no need to store" → chat_only.
7. If confidence < 0.55 and between create_note vs something else → request_clarification.
8. note_type: "task" for actionable items (action verbs: need to, buy, fix, implement, do); "idea" for creative/speculative thoughts; "journal" for diary-style; "note" for everything else.
9. Prefer existing vault folders from VAULT FOLDER STRUCTURE above over creating new ones when content fits naturally.

VAULT TOPICS AVAILABLE:
{topics_hint}

USER MESSAGE:
{message}

Return ONLY the JSON object."""


def _extract_json(raw: str) -> dict:
    """Robustly extract JSON dict from AI response.

    Handles:
    - <think>...</think> blocks (Qwen3, DeepSeek-R1 thinking models)
    - JSON without wrapping {} (model emits bare key-value pairs)
    - Preamble text before the JSON object
    """
    # 1. Strip thinking blocks
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    # 2. Try standard extraction: find first { ... last }
    json_start = text.find("{")
    json_end = text.rfind("}") + 1
    if json_start != -1 and json_end > json_start:
        try:
            return json.loads(text[json_start:json_end])
        except json.JSONDecodeError:
            pass  # fall through to repair attempts

    # 3. Model returned bare JSON fields without {} — wrap and retry
    if '"intent"' in text:
        # Find where the key-value block starts (first " on a line)
        block_start = text.find('"intent"')
        if block_start == -1:
            block_start = 0
        # Find where it ends: last value before any trailing text
        # Heuristic: last line that looks like JSON value
        lines = text[block_start:].strip().splitlines()
        json_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped and (stripped.startswith('"') or stripped[0] in '0123456789-[{tfn'):
                json_lines.append(line)
            elif stripped.startswith("}"):
                break
        if json_lines:
            # Remove trailing comma from last field if present
            last = json_lines[-1].rstrip()
            if last.endswith(","):
                json_lines[-1] = last[:-1]
            candidate = "{\n" + "\n".join(json_lines) + "\n}"
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

    raise ValueError(f"No JSON in response: {raw[:200]!r}")


def route(message: str, provider, vault_index=None, locale: str = "en") -> ActionPlan:
    """Semantically route message via AI. Raises on any failure — no fallback."""
    topics_hint = _topics_hint(vault_index)
    structure_hint = _structure_hint(vault_index)
    prompt = (
        _ROUTER_SYSTEM
        .replace("{locale}", locale)
        .replace("{structure_hint}", structure_hint)
        .replace("{topics_hint}", topics_hint)
        .replace("{message}", message)
    )
    import time as _time
    logger.info("router: sending to AI (message=%.60r)…", message)
    _t0 = _time.monotonic()
    raw = provider.complete(prompt, max_tokens=1500)
    _elapsed = _time.monotonic() - _t0
    logger.info("router: AI responded in %.1fs (%d chars)", _elapsed, len(raw))
    logger.debug("router: raw response: %.300s", raw)
    if not raw or not raw.strip():
        model = getattr(provider, "_model", "unknown")
        raise ValueError(
            f"Model '{model}' returned an empty response to the router prompt. "
            "The model may be ignoring the JSON instruction. "
            "Try setting a larger max_tokens or use a different model."
        )
    data = _extract_json(raw)

    intent_str = data.get("intent", "create_note")
    try:
        intent = Intent(intent_str)
    except ValueError:
        logger.warning("Unknown intent %r — defaulting to create_note", intent_str)
        intent = Intent.CREATE_NOTE

    # Enforce consistency: no-save intents must have should_save=false
    should_save = bool(data.get("should_save", False))
    if intent in _NO_SAVE_INTENTS:
        should_save = False

    # content is only meaningful for save intents
    content = str(data.get("content", "")) if should_save else ""

    plan = ActionPlan(
        intent=intent,
        confidence=float(data.get("confidence", 0.7)),
        should_save=should_save,
        needs_web=bool(data.get("needs_web", False)),
        needs_clarification=bool(data.get("needs_clarification", False)),
        note_type=str(data.get("note_type", "note")),
        general_category=str(data.get("general_category", "")) or "",
        target_folder=str(data.get("target_folder", "General")) or "General",
        target_subfolder=str(data.get("target_subfolder", "")),
        section=str(data.get("section", "")),
        topic=str(data.get("topic", "General")),
        tags=list(data.get("tags", [])),
        summary=str(data.get("summary", "")),
        actions=list(data.get("actions", [intent_str])),
        sources=list(data.get("sources", [])),
        reason=str(data.get("reason", "")),
        title=str(data.get("title", "")) or message[:60],
        content=content,
    )

    logger.info(
        "router: intent=%s confidence=%.2f should_save=%s path=%s | %s",
        plan.intent.value, plan.confidence, plan.should_save,
        _full_path(plan), plan.reason,
    )
    return plan


def _full_path(plan: ActionPlan) -> str:
    """Build the folder path string for logging."""
    parts = [p for p in [plan.general_category, plan.target_folder, plan.target_subfolder, plan.section] if p]
    return "/".join(parts) if parts else plan.target_folder


def _topics_hint(vault_index) -> str:
    if vault_index and vault_index.topics:
        return "Known topics: " + ", ".join(vault_index.topics[:25])
    return "No existing topics yet."


def _structure_hint(vault_index) -> str:
    if vault_index and vault_index.vault_path:
        try:
            from vault_writer.vault.structure import get_structure_hint
            hint = get_structure_hint(vault_index.vault_path)
            return hint
        except Exception as exc:
            logger.debug("_structure_hint failed: %s", exc)
    return "No existing structure yet."
