# Quickstart: BrainSync Media Support (v1.1)

**Branch**: `002-media-support` | **Date**: 2026-03-31

---

## Prerequisites

- BrainSync v1.0 fully configured and running (see `specs/001-brainsync-mvp/quickstart.md`)
- **ffmpeg installed and on PATH** — required for voice message decoding

### Install ffmpeg (Windows)

```bat
winget install ffmpeg
```

Or download from https://ffmpeg.org/download.html and add to PATH.

Verify: `ffmpeg -version`

---

## New Dependencies

```bat
pip install faster-whisper pypdf
```

> `faster-whisper` downloads the transcription model (~466 MB for `small`) on **first bot start**.
> This is a one-time operation. The bot will block all messages until the download completes.

---

## Config Changes

Add to your existing `config.yaml`:

```yaml
ai:
  # ... existing fields ...
  ollama_vision_model: ""     # Set to e.g. "llava" if using Ollama for photos

media:
  max_voice_duration_seconds: 300
  transcription_model: "small"
  pdf_max_pages: 50
  pdf_ai_context_chars: 3000
  max_file_size_mb: 20
```

---

## Supported Media Types

| Type | How to send | Result |
|------|-------------|--------|
| Voice message | Hold mic button in Telegram | Transcribed → note |
| Photo | Camera or gallery | AI description → note |
| PDF | Attach file | Extracted text → note |
| `.txt` / `.md` | Attach file | Content → note |
| Video, sticker, GIF | ❌ Not supported | Friendly error message |

---

## Using Captions as Prefixes

Any supported prefix works as a Telegram caption on media:

```
задача: купити молоко     ← caption on voice → saves as task note
ідея: ця фотка нагадала  ← caption on photo → saves as idea note
```

Without a caption prefix, the content is classified automatically by AI.

---

## Ollama Vision Setup

To use Ollama for photo processing (fully offline):

1. Pull a vision model:
   ```bash
   ollama pull llava
   ```

2. Set in `config.yaml`:
   ```yaml
   ai:
     provider: "ollama"
     model: "mistral"            # text model for classification
     ollama_vision_model: "llava" # vision model for photos
   ```

3. Restart the bot.

> Without `ollama_vision_model` set, photos fall back to caption-only saving with a notification.

---

## Validation Checklist

- [ ] `ffmpeg -version` returns a version (no "not found")
- [ ] `pip show faster-whisper` and `pip show pypdf` both installed
- [ ] `config.yaml` has `media:` block with all required fields
- [ ] Start bot → on first run: "завантаження моделі" notification received in Telegram
- [ ] After model download: "✅ Модель готова" notification received
- [ ] Send a voice message → vault note created with transcript content
- [ ] Send a photo → vault note created with image description
- [ ] Send a PDF → vault note created with extracted text
- [ ] Send a `.txt` file → vault note created with file content
- [ ] Send a video → bot replies with unsupported type message
- [ ] Send a voice longer than `max_voice_duration_seconds` → bot replies with duration error
