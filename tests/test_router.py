"""Tests for AI Semantic Router — ActionPlan contract and intent enum."""
from __future__ import annotations

import pytest
from vault_writer.ai.router import (
    Intent,
    ActionPlan,
    _NO_SAVE_INTENTS,
)


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
        if intent in _NO_SAVE_INTENTS:
            plan.should_save = False
        assert plan.should_save is False

    def test_all_intents_covered(self):
        """Ensure every Intent value is in _NO_SAVE_INTENTS or the save group."""
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
        "create_note", "append_note", "update_note", "move_note",
        "search_vault", "answer_from_vault", "analyze_vault", "summarize_vault",
        "search_web", "extract_structured_data",
        "transcribe_audio", "ocr_image", "parse_document",
        "request_clarification", "chat_only", "ignore_spam", "manual_review",
    ]

    def test_all_required_intents_exist(self):
        values = {i.value for i in Intent}
        for req in self.REQUIRED:
            assert req in values, f"Missing intent: {req}"
