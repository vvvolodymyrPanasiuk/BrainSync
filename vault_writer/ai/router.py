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


def route(message: str, provider, vault_index=None) -> ActionPlan:
    """Semantically route message via AI. Falls back to heuristic on failure."""
    topics_hint = _topics_hint(vault_index)

    try:
        prompt = _ROUTER_SYSTEM.format(message=message, topics_hint=topics_hint)
        raw = provider.complete(prompt, max_tokens=450)

        json_start = raw.find("{")
        json_end = raw.rfind("}") + 1
        if json_start == -1 or json_end == 0 or json_start >= json_end:
            raise ValueError(f"No JSON in response: {raw[:200]!r}")

        data = json.loads(raw[json_start:json_end])

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

    # Chat / greetings
    if _has(["привіт", "вітаю", "добрий", "як справи", "дякую", "окей",
             "зрозуміло", "чудово", "бувай", "hello", "hey", "thanks",
             "thank you", "okay", "не треба", "просто питання"]):
        return _make_plan(Intent.CHAT_ONLY, False, message)

    # Short questions → likely chat
    if text.endswith("?") and len(text) < 120:
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
