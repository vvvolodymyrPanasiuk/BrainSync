"""Intent classification: classify plain-text messages into IntentType."""
from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    RAG_QUERY    = "rag_query"     # "що я думав про CQRS?"
    SEARCH_QUERY = "search_query"  # "знайди нотатки про X"
    CHAT         = "chat"          # casual message, question to AI, not worth saving
    NEW_NOTE     = "new_note"      # default: save as note


_INTENT_PROMPT = """\
Classify the following user message into exactly one category:

- rag_query: The user asks about their own notes/vault — wants an answer synthesized \
from their stored knowledge, or asks what they thought/wrote about something. \
Examples: "що я думав про CQRS?", "як я вирішував проблему X?", "розкажи про мої думки щодо Y"

- search_query: The user explicitly wants to find or list notes in the vault. \
Examples: "знайди нотатки про X", "покажи все про Y", "є щось про Z?", "пошукай записи"

- chat: The user is having casual conversation, asking the AI a general question \
(not about the vault), greeting, testing, saying something that is NOT a thought/idea/task \
worth saving. Examples: "привіт", "як справи?", "що таке CQRS?" (general knowledge question), \
"це просто тест", "дякую", "добре", "окей", "які твої можливості?"

- new_note: The user is sharing a thought, idea, insight, task, plan, observation, \
or any content that represents knowledge worth capturing and saving permanently. \
Examples: "дізнався що Redis підтримує pub/sub", "треба купити молоко", \
"ідея для нового проекту — автоматизувати X", "сьогодні зрозумів що Y"

User message: {message}

Reply with exactly one word: rag_query, search_query, chat, or new_note"""


def classify_intent(message: str, provider) -> IntentType:
    """Classify user message intent using AI. Falls back to heuristic on any error."""
    try:
        prompt = _INTENT_PROMPT.format(message=message)
        response = provider.complete(prompt, max_tokens=20)
        cleaned = response.strip().lower().split()[0] if response.strip() else ""
        for intent in IntentType:
            if intent.value == cleaned:
                logger.debug("Intent classified: %s for message: %.50s", cleaned, message)
                return intent
        logger.debug("Unrecognised intent response %r — defaulting to new_note", response)
        return IntentType.NEW_NOTE
    except Exception as exc:
        logger.warning("Intent classification failed (%s) — using heuristic fallback", exc)
        return _heuristic_intent(message)


def _heuristic_intent(message: str) -> IntentType:
    """Rule-based intent classifier used when AI is unavailable."""
    import re
    text = message.strip().lower()

    def _has(phrases: list[str]) -> bool:
        """True if any phrase appears as a whole token (not inside another word)."""
        for phrase in phrases:
            # For multi-word phrases a simple substring is fine
            if " " in phrase:
                if phrase in text:
                    return True
            else:
                # Single word: require word boundary
                if re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text):
                    return True
        return False

    # RAG: asking about own notes/vault
    if _has([
        "що я думав", "що я писав", "як я вирішував", "мої думки",
        "мої нотатки", "у моїх нотатках", "розкажи про мої",
        "what did i think", "what did i write", "my notes",
    ]):
        return IntentType.RAG_QUERY

    # Search: explicit find/search request
    if _has([
        "знайди", "пошукай", "покажи все про", "є щось про", "є нотатки про",
        "find notes", "search for", "show me notes",
    ]):
        return IntentType.SEARCH_QUERY

    # Chat: greetings, questions to AI, short casual messages
    if _has([
        "привіт", "вітаю", "добрий день", "добрий ранок", "як справи",
        "дякую", "окей", "зрозуміло", "чудово", "бувай",
        "hello", "hey", "thanks", "thank you", "okay",
        "не треба", "не записуй", "не зберігай",
        "просто тест", "просто питання",
    ]):
        return IntentType.CHAT

    # Short question → AI question, not worth saving
    if text.endswith("?") and len(text) < 120:
        return IntentType.CHAT

    return IntentType.NEW_NOTE
