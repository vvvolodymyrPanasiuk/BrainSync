# Implementation Plan: BrainSync — Media & File Capture Support

**Branch**: `002-media-support` | **Date**: 2026-03-31 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/002-media-support/spec.md`

---

## Summary

Extend the existing BrainSync Telegram bot with support for voice messages, photos, PDF documents, and plain text files. All processing is local and free after initial model download: voice is transcribed on-device via `faster-whisper`; PDFs are parsed locally via `pypdf`; images are described by the already-configured AI provider (Anthropic vision or Ollama multimodal). The Ollama provider stub is replaced with a full implementation for both text and vision. All media output feeds into the existing note pipeline unchanged.

---

## Technical Context

**Language/Version**: Python 3.12+ on Windows 11
**Primary Dependencies (new)**: `faster-whisper` (voice transcription), `pypdf` (PDF extraction); `ffmpeg` system binary (required by faster-whisper for .ogg decoding)
**Primary Dependencies (existing)**: `python-telegram-bot>=20.0`, `anthropic`, `mcp`, `pyyaml`, `gitpython`
**Storage**: Local filesystem (vault .md files), model cache (~466 MB for `small` Whisper model)
**Testing**: pytest (existing)
**Target Platform**: Windows 11, Python 3.12+
**Project Type**: Telegram bot daemon (single-process, single-user)
**Performance Goals**: Voice ≤30s for 60s audio; Photo ≤15s; PDF ≤20s for 10 pages (SC-101–103)
**Constraints**: No external APIs beyond already-configured AI provider; fully offline after model download; no new credentials required
**Scale/Scope**: Single user, single bot instance

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Local-First Architecture | ✅ PASS | All new processing (transcription, PDF extraction) is on-device. Vision uses already-configured provider. No new external services. |
| II. AI as Intelligence Layer Only | ✅ PASS | Transcription and PDF extraction are deterministic (not AI). Image description and note classification remain AI-only tasks. |
| III. Provider Abstraction | ✅ PASS | `AIProvider` extended with optional `complete_with_image()`. `AnthropicProvider` and `OllamaProvider` implement it. No direct library imports outside provider classes. |
| IV. VaultWriter as Single Write Gateway | ✅ PASS | Media handler outputs text/content and calls existing `handle_create_note` — no direct vault writes from `telegram/handlers/media.py`. |
| V. Config Drives Behavior | ✅ PASS | New fields added to `config.yaml` (`ai.ollama_vision_model`, `media.*` block). No prose AI instructions in config. |
| Security & Privacy | ✅ PASS | Auth check enforced in media handler. Downloaded media files deleted after processing. |

**No violations. Proceeding to Phase 0.**

---

## Project Structure

### Documentation (this feature)

```text
specs/002-media-support/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   └── config-schema.md ← updated schema with media block
└── tasks.md             ← Phase 2 output (/speckit.tasks)
```

### Source Code Changes

```text
# Modified files
config/loader.py                          # MediaConfig dataclass + new fields
vault_writer/ai/provider.py               # add complete_with_image() to AIProvider
vault_writer/ai/anthropic_provider.py     # implement complete_with_image()
vault_writer/ai/ollama_provider.py        # full implementation (text + vision)
telegram/bot.py                           # register voice/photo/document handlers
telegram/formatter.py                     # media error messages
main.py                                   # infrastructure readiness check at startup

# New files
vault_writer/ai/transcriber.py            # faster-whisper voice-to-text
vault_writer/media/pdf_extractor.py       # pypdf text extraction
vault_writer/media/__init__.py
telegram/handlers/media.py                # unified media message handler
```

**Structure Decision**: Single project layout preserved from v1.0. New `vault_writer/media/` sub-package added for non-AI media processing (PDF, future formats). Media handling stays in `telegram/handlers/` following existing handler pattern.

---

## Complexity Tracking

No constitution violations to justify. No complexity table needed.
