"""Intent classification: classify plain-text messages into IntentType."""
from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    RAG_QUERY    = "rag_query"     # "що я думав про X?"
    SEARCH_QUERY = "search_query"  # "знайди нотатки про X"
    NEW_NOTE     = "new_note"      # default: save as note


_INTENT_PROMPT = """\
Classify the following user message into exactly one category:

- rag_query: The user is asking a question about their own notes/vault, \
wants an answer synthesized from their stored knowledge, or asks what they thought/wrote about something. \
Examples: "що я думав про CQRS?", "як я вирішував проблему кешування?", "розкажи мені про мої думки щодо X"

- search_query: The user explicitly wants to find or list notes, \
is searching for something specific in the vault. \
Examples: "знайди нотатки про X", "покажи все про Y", "є щось про Z?", "пошукай записи про"

- new_note: Everything else — the user is sharing a thought, idea, task, journal entry, \
or any content they want saved as a new note.

User message: {message}

Reply with exactly one word: rag_query, search_query, or new_note"""


def classify_intent(message: str, provider) -> IntentType:
    """Classify user message intent using AI. Returns NEW_NOTE on any error (safe default)."""
    try:
        prompt = _INTENT_PROMPT.format(message=message)
        response = provider.complete(prompt, max_tokens=20)
        cleaned = response.strip().lower().split()[0] if response.strip() else ""
        for intent in IntentType:
            if intent.value == cleaned:
                logger.debug("Intent classified: %s for message snippet: %.50s", cleaned, message)
                return intent
        logger.debug("Unrecognised intent response %r — defaulting to new_note", response)
        return IntentType.NEW_NOTE
    except Exception as exc:
        logger.warning("Intent classification failed (%s) — defaulting to new_note", exc)
        return IntentType.NEW_NOTE
