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
    note_type: str          # note | task | idea | journal
    target_folder: str      # main topic folder
    target_subfolder: str   # optional sub-topic (else "")
    topic: str
    tags: list[str]
    summary: str
    actions: list[str]
    sources: list[str]
    reason: str
    title: str = ""


_ROUTER_SYSTEM = """\
You are the intent routing component of BrainSync — a personal Telegram→Obsidian AI assistant.

Analyze the user message and return ONLY a JSON object with this exact structure:

{
  "intent": "<one of the allowed intents>",
  "confidence": <0.0-1.0>,
  "should_save": <true|false>,
  "needs_web": <true|false>,
  "needs_clarification": <true|false>,
  "note_type": "<note|task|idea|journal>",
  "target_folder": "<main topic folder name>",
  "target_subfolder": "<sub-topic if any, else empty string>",
  "topic": "<topic in 1-3 words>",
  "tags": ["<tag1>", "<tag2>"],
  "summary": "<1 sentence summary>",
  "actions": ["<primary_action>"],
  "sources": [],
  "reason": "<1 sentence explanation>",
  "title": "<short note title if creating a note, else empty string>"
}

ALLOWED INTENTS:
- create_note: User shares a new thought, idea, task, learning, insight, journal entry or content worth saving. should_save=true.
- append_note: User wants to add content to an existing note. should_save=true.
- update_note: User wants to correct/update an existing note. should_save=true.
- search_vault: User wants to find/list/browse notes ("знайди нотатки про X", "є щось про Y?"). should_save=false.
- answer_from_vault: User asks about their own notes/thoughts ("що я думав про X?", "що я писав про Y?", "як я вирішував Z?"). should_save=false.
- analyze_vault: User wants broad vault analysis ("що в мене є?", "що у сховищі?", "проаналізуй мої нотатки", "які теми?"). should_save=false.
- summarize_vault: User wants a summary of recent or topic notes. should_save=false.
- search_web: User explicitly needs external information. Use only if vault clearly cannot satisfy. should_save=false.
- extract_structured_data: User provides structured data (table, receipt, CSV) to parse. should_save=true.
- move_note: User wants to move/relocate an existing note to a different folder. target_folder=DESTINATION folder. should_save=false.
- request_clarification: Message is too ambiguous to route. should_save=false.
- chat_only: Casual talk, greeting, thanks, test, general AI question NOT about vault content. should_save=false.
- ignore_spam: Random characters, obvious spam, noise. should_save=false.
- manual_review: Sensitive/medical/legal content. should_save=false.

CRITICAL RULES:
1. NOT every message should be saved. Only create_note/append_note/update_note/extract_structured_data → should_save=true.
2. "Що у мене є?", "що є в сховищі?", "проаналізуй все" → analyze_vault, should_save=false.
3. Questions about what user thought/wrote → answer_from_vault, should_save=false.
4. Greetings, "дякую", "окей", "це тест", "не записуй" → chat_only, should_save=false.
5. Short questions ending in "?" about external knowledge (not vault) → chat_only.
6. "Не записуй це", "просто питання", "не треба зберігати" → chat_only.
7. If confidence < 0.55 and between create_note vs something else → request_clarification.
8. target_folder: meaningful topic name in user's language matching content (e.g., "Програмування", "Здоров'я", "Фінанси", "Ідеї", "Programming").
9. note_type: "task" for actionable items with verbs like "треба", "зробити", "купити"; "idea" for creative/speculative thoughts; "journal" for diary-style; "note" for everything else.

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


def route(message: str, provider, vault_index=None) -> ActionPlan:
    """Semantically route message via AI. Falls back to heuristic on failure."""
    topics_hint = _topics_hint(vault_index)

    try:
        prompt = _ROUTER_SYSTEM.format(message=message, topics_hint=topics_hint)
        import time as _time
        logger.info("router: sending to AI (message=%.60r)…", message)
        _t0 = _time.monotonic()
        raw = provider.complete(prompt, max_tokens=1500)
        _elapsed = _time.monotonic() - _t0
        logger.info("router: AI responded in %.1fs (%d chars)", _elapsed, len(raw))
        logger.debug("router: raw response: %.300s", raw)
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

        plan = ActionPlan(
            intent=intent,
            confidence=float(data.get("confidence", 0.7)),
            should_save=should_save,
            needs_web=bool(data.get("needs_web", False)),
            needs_clarification=bool(data.get("needs_clarification", False)),
            note_type=str(data.get("note_type", "note")),
            target_folder=str(data.get("target_folder", "General")) or "General",
            target_subfolder=str(data.get("target_subfolder", "")),
            topic=str(data.get("topic", "General")),
            tags=list(data.get("tags", [])),
            summary=str(data.get("summary", "")),
            actions=list(data.get("actions", [intent_str])),
            sources=list(data.get("sources", [])),
            reason=str(data.get("reason", "")),
            title=str(data.get("title", "")) or message[:60],
        )

        logger.info(
            "router: intent=%s confidence=%.2f should_save=%s folder=%s | %s",
            plan.intent.value, plan.confidence, plan.should_save,
            plan.target_folder, plan.reason,
        )
        return plan

    except Exception as exc:
        logger.warning("router AI call failed (%s) — heuristic fallback", exc)
        return _heuristic_route(message)


def _topics_hint(vault_index) -> str:
    if vault_index and vault_index.topics:
        return "Known topics: " + ", ".join(vault_index.topics[:25])
    return "No existing topics yet."


def _heuristic_route(message: str) -> ActionPlan:
    """Emergency fallback when AI is completely unavailable."""
    text = message.strip().lower()

    def _has(phrases: list[str]) -> bool:
        for phrase in phrases:
            if " " in phrase:
                if phrase in text:
                    return True
            else:
                if re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text):
                    return True
        return False

    # Explicit no-save
    if _has(["не записуй", "не зберігай", "просто тест", "це тест",
             "не треба записувати", "не треба зберігати"]):
        return _make_plan(Intent.CHAT_ONLY, False, message)

    # Vault-wide analysis
    if _has(["що у мене є", "що є в сховищі", "що є у сховищі",
             "що в моєму сховищі", "проаналізуй все", "аналіз сховища",
             "покажи vault", "що містить сховище", "які теми є"]):
        return _make_plan(Intent.ANALYZE_VAULT, False, message)

    # Vault answer (about user's own thoughts)
    if _has(["що я думав", "що я писав", "як я вирішував", "мої думки",
             "мої нотатки", "у моїх нотатках", "розкажи про мої",
             "what did i think", "what did i write", "my notes"]):
        return _make_plan(Intent.ANSWER_FROM_VAULT, False, message)

    # Vault search
    if _has(["знайди", "пошукай", "покажи все про", "є щось про",
             "є нотатки про", "find notes", "search for"]):
        return _make_plan(Intent.SEARCH_VAULT, False, message)

    # Move note commands
    if _has(["перемісти нотатку", "перенеси нотатку", "переміщення нотатки",
             "move note", "move to folder", "перемісти в папку", "перенеси в папку"]):
        return _make_plan(Intent.MOVE_NOTE, False, message)

    # Chat / greetings
    if _has(["привіт", "вітаю", "добрий", "як справи", "дякую", "окей",
             "зрозуміло", "чудово", "бувай", "hello", "hey", "thanks",
             "thank you", "okay", "не треба", "просто питання"]):
        return _make_plan(Intent.CHAT_ONLY, False, message)

    # Messages starting with question words → likely a clarification/chat, not a note
    if re.match(
        r"^(чому|навіщо|чим відрізняється|як так|як це так|чи правильно|чи можеш|хіба|"
        r"what is|why did|why is|how come|why are|isn't it)",
        text,
    ):
        return _make_plan(Intent.CHAT_ONLY, False, message)

    # Questions ending with "?" → likely chat (extended limit to 400 chars)
    if text.endswith("?") and len(text) < 400:
        return _make_plan(Intent.CHAT_ONLY, False, message)

    # Default: save
    return _make_plan(Intent.CREATE_NOTE, True, message)


def _make_plan(intent: Intent, should_save: bool, message: str) -> ActionPlan:
    return ActionPlan(
        intent=intent,
        confidence=0.5,
        should_save=should_save,
        needs_web=False,
        needs_clarification=False,
        note_type="note",
        target_folder="General",
        target_subfolder="",
        topic="General",
        tags=[],
        summary=message[:100],
        actions=[intent.value],
        sources=[],
        reason="heuristic fallback (AI unavailable)",
        title=message[:60],
    )
