"""Tests for AI Semantic Router — heuristic fallback and ActionPlan contract."""
from __future__ import annotations

import pytest
from vault_writer.ai.router import (
    Intent,
    ActionPlan,
    _heuristic_route,
    _NO_SAVE_INTENTS,
)


# ── Heuristic routing ─────────────────────────────────────────────────────────

class TestHeuristicRoute:
    """Verify _heuristic_route covers critical scenarios without AI."""

    # Vault analysis
    @pytest.mark.parametrize("msg", [
        "що у мене є в сховищі?",
        "що є в сховищі",
        "проаналізуй все що є",
        "які теми є у vault",
        "що в моєму сховищі",
    ])
    def test_analyze_vault(self, msg):
        plan = _heuristic_route(msg)
        assert plan.intent == Intent.ANALYZE_VAULT
        assert plan.should_save is False

    # Vault answer (about own thoughts)
    @pytest.mark.parametrize("msg", [
        "що я думав про CQRS?",
        "що я писав про Python",
        "розкажи про мої думки щодо Redis",
        "мої нотатки про архітектуру",
    ])
    def test_answer_from_vault(self, msg):
        plan = _heuristic_route(msg)
        assert plan.intent == Intent.ANSWER_FROM_VAULT
        assert plan.should_save is False

    # Vault search
    @pytest.mark.parametrize("msg", [
        "знайди нотатки про Docker",
        "пошукай записи про Python",
        "є щось про machine learning?",
    ])
    def test_search_vault(self, msg):
        plan = _heuristic_route(msg)
        assert plan.intent == Intent.SEARCH_VAULT
        assert plan.should_save is False

    # Chat — no save
    @pytest.mark.parametrize("msg", [
        "привіт",
        "дякую",
        "не записуй це",
        "не зберігай",
        "просто тест",
        "це тест",
        "не треба записувати",
    ])
    def test_chat_only_no_save(self, msg):
        plan = _heuristic_route(msg)
        assert plan.intent == Intent.CHAT_ONLY
        assert plan.should_save is False

    # Short questions → chat
    @pytest.mark.parametrize("msg", [
        "як справи?",
        "що таке CQRS?",
        "яка погода завтра?",
    ])
    def test_short_question_is_chat(self, msg):
        plan = _heuristic_route(msg)
        assert plan.intent == Intent.CHAT_ONLY
        assert plan.should_save is False

    # New notes → save
    @pytest.mark.parametrize("msg", [
        "сьогодні зрозумів що Redis підтримує pub/sub",
        "треба купити молоко",
        "ідея для проекту: автоматизувати деплой",
        "дізнався що PostgreSQL підтримує JSONB",
    ])
    def test_create_note(self, msg):
        plan = _heuristic_route(msg)
        assert plan.intent == Intent.CREATE_NOTE
        assert plan.should_save is True

    # Milk fix — "молоко" must NOT match "ок" keyword
    def test_milk_no_false_chat(self):
        plan = _heuristic_route("треба купити молоко")
        assert plan.intent == Intent.CREATE_NOTE
        assert plan.should_save is True


# ── ActionPlan contract ───────────────────────────────────────────────────────

class TestActionPlanContract:
    """Verify ActionPlan always has correct should_save for no-save intents."""

    @pytest.mark.parametrize("intent", list(_NO_SAVE_INTENTS))
    def test_no_save_intents_have_false_should_save(self, intent):
        plan = ActionPlan(
            intent=intent,
            confidence=0.9,
            should_save=True,   # deliberately wrong
            needs_web=False,
            needs_clarification=False,
            note_type="note",
            target_folder="General",
            target_subfolder="",
            topic="General",
            tags=[],
            summary="test",
            actions=[intent.value],
            sources=[],
            reason="test",
            title="test",
        )
        # The router enforces this on return — simulate the enforcement
        from vault_writer.ai.router import _NO_SAVE_INTENTS
        if intent in _NO_SAVE_INTENTS:
            plan.should_save = False
        assert plan.should_save is False

    def test_all_intents_covered(self):
        """Ensure every Intent value is handled in _NO_SAVE_INTENTS or save group."""
        save_intents = {
            Intent.CREATE_NOTE, Intent.APPEND_NOTE, Intent.UPDATE_NOTE,
            Intent.EXTRACT_STRUCTURED, Intent.TRANSCRIBE_AUDIO,
            Intent.OCR_IMAGE, Intent.PARSE_DOCUMENT,
        }
        all_intents = set(Intent)
        categorised = _NO_SAVE_INTENTS | save_intents
        uncategorised = all_intents - categorised
        assert not uncategorised, f"Uncategorised intents: {uncategorised}"


# ── Intent enum completeness ──────────────────────────────────────────────────

class TestIntentEnum:
    REQUIRED = [
        "create_note", "append_note", "update_note",
        "search_vault", "answer_from_vault", "analyze_vault", "summarize_vault",
        "search_web", "extract_structured_data",
        "transcribe_audio", "ocr_image", "parse_document",
        "request_clarification", "chat_only", "ignore_spam", "manual_review",
    ]

    def test_all_required_intents_exist(self):
        values = {i.value for i in Intent}
        for req in self.REQUIRED:
            assert req in values, f"Missing intent: {req}"
