# Feature Specification: BrainSync — Media & File Capture Support

**Feature Branch**: `002-media-support`
**Created**: 2026-03-31
**Status**: Draft
**Input**: User description: "дооробити поточну реалізацію, щоб працювало медіа, файли, голосові, PDF. Реалізація має бути безкоштовна без стороніх апі. також не забувай що має підтримуватись ollama моделі"

---

## Clarifications

### Session 2026-03-31

- Q: When the transcription model is downloading and a voice message arrives, what should happen? → A: Block the bot entirely during download — no messages of any type are processed until all required infrastructure (transcription model) is ready; a progress notification is sent to the user.
- Q: What Ollama config fields should be added to config.yaml? → A: Two new fields under the existing `[ai]` block: `ollama_base_url` (default: `http://localhost:11434`) for the text/classification model endpoint, and `ollama_vision_model` (optional) for a separate vision-capable model used for photo processing.
- Q: How should large PDF text be handled before sending to AI? → A: Save the full extracted text to the vault note body unchanged; send only the first N characters (configurable, e.g. 3000) to AI for classification and title generation. The note preserves complete content while AI costs remain bounded.
- Q: How should photo processing work with Anthropic provider — same model or separate vision model config? → A: Use the same `ai.model` already configured for text. If the model returns an error indicating vision is unsupported, fall back to caption-only note saving and notify the user. No additional config field required.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Capture Voice Message as Vault Note (Priority: P1)

The user records and sends a voice message to the Telegram bot. The system transcribes the audio locally using an on-device model (no external API), then processes the transcript through the existing note pipeline — classification, formatting, vault write — and replies with the saved file path.

**Why this priority**: Voice capture is the most natural mobile input. Removing the friction of typing makes the tool significantly more usable on-the-go. This is the most demanded media type.

**Independent Test**: Send a 10–30 second voice message to the bot; verify a structured `.md` file appears in the vault containing the transcribed content as the note body.

**Acceptance Scenarios**:

1. **Given** the bot is running and the user is authorised,
   **When** the user sends a voice message (any duration up to the configured limit),
   **Then** the system transcribes the audio locally, classifies the content, writes a structured note to the vault, and replies with `✓ Збережено → {file_path}`.

2. **Given** the user sends a voice message with a caption (e.g. `задача:` added as the Telegram caption),
   **Then** the caption is treated as an inline prefix and the note is saved with the correct type without additional AI classification.

3. **Given** a voice message exceeds the configured maximum duration,
   **Then** the bot replies with a clear error message stating the limit and does NOT save a partial note.

4. **Given** the transcription model has not yet been downloaded when the bot starts,
   **Then** the bot sends a startup notification ("завантаження моделі транскрипції, зачекайте…"), blocks ALL incoming messages until the download completes, then sends a ready notification and resumes normal operation.

---

### User Story 2 — Capture Photo/Image as Vault Note (Priority: P2)

The user sends a photo to the Telegram bot, optionally with a caption. The system describes the image using the already-configured AI provider (local Ollama or cloud Anthropic), combines the description with the caption, and saves a structured note to the vault.

**Why this priority**: Photos of whiteboards, documents, and diagrams are common knowledge-capture moments. No new credentials are required — the existing AI provider handles it.

**Independent Test**: Send a photo of a whiteboard or handwritten note; verify the vault note contains a meaningful description of the image content.

**Acceptance Scenarios**:

1. **Given** the user sends a photo without a caption,
   **Then** the system generates a textual description of the image, classifies it, saves a structured note, and replies with the file path.

2. **Given** the user sends a photo with a caption,
   **Then** the caption is combined with the image description as the note content; any prefix in the caption is used for type detection.

3. **Given** the AI provider is Ollama with a vision-capable model configured,
   **Then** image description is performed entirely on-device without any internet request.

4. **Given** the AI provider is Anthropic with a vision-capable model,
   **Then** image description is performed via the existing API key — no new key required.

5. **Given** the image cannot be processed (corrupt file, unsupported format),
   **Then** the bot saves a note using only the caption text (if present) and notifies the user that image processing failed.

---

### User Story 3 — Capture PDF Document as Vault Note (Priority: P3)

The user sends a PDF file to the bot. The system extracts the text content locally without any external service, then saves a structured note with the extracted content.

**Why this priority**: PDFs are a common format for articles, papers, and reference material. Local extraction keeps the implementation fully offline and free.

**Independent Test**: Send a PDF article (2–10 pages); verify a vault note is created with the extracted text as the body.

**Acceptance Scenarios**:

1. **Given** the user sends a PDF file with selectable text,
   **Then** the system extracts the text locally, processes it through the note pipeline, saves a structured note, and replies with the file path.

2. **Given** the PDF exceeds the configured page limit,
   **Then** the system extracts only up to the configured limit and notifies the user that the document was truncated.

3. **Given** the PDF contains only scanned images (no selectable text),
   **Then** the bot notifies the user that the document could not be parsed and does NOT save an empty note.

4. **Given** the PDF has a meaningful filename,
   **Then** the filename is used as a fallback note title when no better title is found in the content.

---

### User Story 4 — Capture Plain Text File as Vault Note (Priority: P4)

The user sends a plain text file (`.txt`, `.md`) to the bot. The system reads the content directly and saves it as a structured vault note.

**Why this priority**: Text files require zero special processing and cover a broad set of use cases (exported notes, copied articles, code snippets).

**Independent Test**: Send a `.txt` file containing notes; verify the content appears in a structured vault note.

**Acceptance Scenarios**:

1. **Given** the user sends a `.txt` or `.md` file,
   **Then** the system reads the content, processes it through the note pipeline, and saves a structured note.

2. **Given** the file exceeds the configured size limit,
   **Then** the bot notifies the user and does NOT save a partial note.

3. **Given** an unsupported file type is sent (e.g., `.zip`, `.exe`),
   **Then** the bot replies listing the supported types and does NOT attempt processing.

---

### User Story 5 — Ollama Full Implementation (Text + Vision) (Priority: P5)

The existing Ollama provider stub (`NotImplementedError`) is replaced with a complete implementation supporting both text completion and multimodal (vision) input when a vision-capable model is configured.

**Why this priority**: Delivers a fully offline, zero-cost path for all processing. Completes the provider abstraction promised in v1.0 but deferred.

**Independent Test**: Configure Ollama with a text model; send a plain message and verify a note is saved. Then configure a vision model and send a photo — verify the note contains an image description. Both tests run with network disabled.

**Acceptance Scenarios**:

1. **Given** Ollama is configured with a text model,
   **When** the user sends any text message,
   **Then** classification and formatting are performed locally via Ollama with no internet request.

2. **Given** Ollama is configured with a vision model,
   **When** the user sends a photo,
   **Then** image description is performed locally via Ollama.

3. **Given** Ollama is configured but the model does not support vision,
   **When** the user sends a photo,
   **Then** the bot notifies the user and falls back to caption-only note saving.

---

### Edge Cases

- If the transcription model is not present at startup, the bot blocks ALL incoming messages (not just voice) until the download completes; no partial processing occurs during initialisation.
- If both a caption and media content are present, the caption takes precedence for type/prefix detection; the media-derived content becomes the note body.
- If a file exceeds Telegram's own download size limit, the bot replies with a clear error and does not attempt a partial download.
- If the AI provider fails during image description, the system falls back to saving only the caption as the note body and notifies the user.
- Unsupported media types (video, sticker, GIF, audio file, contact) receive a friendly reply listing supported types — no silent failures.
- If PDF text extraction produces an empty result after stripping whitespace, the note is not saved and the user is notified.

---

## Requirements *(mandatory)*

### Functional Requirements

**Voice Transcription**

- **FR-101**: The system MUST transcribe voice messages locally using an on-device model with no external API calls after the initial one-time model download.
- **FR-102**: The system MUST enforce a configurable maximum voice message duration; messages exceeding the limit MUST be rejected with a user-facing error.
- **FR-103**: On startup, if the transcription model is not present, the system MUST immediately block all incoming message processing, send a notification to the authorised user ("завантаження моделі…"), download the model, send a ready confirmation, then resume normal operation. No messages MUST be processed while infrastructure is initialising.
- **FR-104**: The transcription output MUST be passed into the existing note pipeline identically to a plain-text message (prefix detection → classification → formatting → vault write).
- **FR-105**: A caption on a voice message MUST be treated as an inline prefix for note type override.

**Image Processing**

- **FR-106**: The system MUST support photo messages using the already-configured AI provider and the same `ai.model` used for text — no additional API key, service, or config field required.
- **FR-107**: When Ollama is the provider and `ai.ollama_vision_model` is configured, image processing MUST be performed entirely on-device using that model.
- **FR-108**: When vision processing fails due to an unsupported model (either Anthropic model error or missing `ai.ollama_vision_model`), the system MUST fall back to caption-only note saving and notify the user with the reason.
- **FR-109**: Photo captions MUST be combined with the AI-generated image description as the full note content.
- **FR-110**: Corrupt or unprocessable images MUST result in a user-facing error; no empty note is saved.

**PDF Processing**

- **FR-111**: The system MUST extract text from PDF files locally with no external service or API.
- **FR-112**: PDF extraction MUST respect a configurable page limit; documents exceeding the limit MUST be truncated with a user notification.
- **FR-113**: PDFs yielding no extractable text MUST result in a user-facing notification; no empty note is saved.
- **FR-114**: The PDF filename MUST be used as a fallback note title when no better title is found.
- **FR-114a**: The full extracted PDF text MUST be written to the vault note body unchanged. Only the first N characters (configurable, default 3000) MUST be sent to the AI for classification and title generation, keeping AI token usage bounded regardless of document length.

**Text File Processing**

- **FR-115**: The system MUST support `.txt` and `.md` file messages by reading their content directly.
- **FR-116**: Files exceeding a configurable size limit MUST be rejected with a user-facing message.
- **FR-117**: Unsupported file types MUST be rejected with a message listing the supported types.

**Ollama Provider**

- **FR-118**: The Ollama provider MUST be fully implemented for text completion, replacing the current stub.
- **FR-119**: The Ollama provider MUST support multimodal (vision) input when `ai.ollama_vision_model` is configured; if absent, photo processing falls back to caption-only.
- **FR-120**: All Ollama requests MUST be directed to `ai.ollama_base_url` (default: `http://localhost:11434`); no external network requests occur after model download.
- **FR-120a**: The configuration schema MUST be extended with two new optional fields under `[ai]`: `ollama_base_url` (string, default `http://localhost:11434`) and `ollama_vision_model` (string, optional). These fields are ignored when `ai.provider` is `anthropic`.

**Bot Integration**

- **FR-121**: The bot MUST register message handlers for: voice, photo, and document (PDF and text files) message types.
- **FR-122**: Unsupported media types (video, sticker, GIF, audio document, contact) MUST receive a user-facing reply listing supported types.
- **FR-123**: During media processing, the bot MUST continuously send a typing indicator until the reply is delivered.
- **FR-124**: All media handlers MUST enforce the existing authorised-user-ID check before any processing.

### Key Entities

- **MediaMessage**: A Telegram message containing non-text content. Attributes: type (voice/photo/document), file ID, file size, duration (voice), caption (optional), MIME type (documents).
- **TranscriptionResult**: Output of voice-to-text conversion. Attributes: transcript text, detected language, duration, model used.
- **ImageDescription**: Output of vision AI processing. Attributes: description text, provider used, model used.
- **ExtractedDocument**: Text content parsed from a file. Attributes: raw text, page count (PDF only), truncated flag, source filename.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-101**: A user can send a voice message up to 60 seconds long and receive a vault note confirmation within 30 seconds (local transcription, balanced processing mode).
- **SC-102**: A user can send a photo and receive a vault note confirmation within 15 seconds (balanced mode, normal conditions).
- **SC-103**: A user can send a PDF up to 10 pages and receive a vault note confirmation within 20 seconds.
- **SC-104**: All media handlers respect the authorised-user policy — unauthorised senders receive no response 100% of the time.
- **SC-105**: No external API calls occur during voice transcription after the one-time model download, verifiable by running with network disabled.
- **SC-106**: When Ollama is configured, the entire workflow (text classification, formatting, image description) runs fully offline once all models are downloaded.
- **SC-107**: Unsupported media types always receive a clear user-facing message — zero silent failures.
- **SC-108**: Existing text-only flows continue to work without any change in behaviour after this feature is deployed.

---

## Assumptions

- The existing BrainSync v1.0 implementation is fully functional; this feature extends it without modifying the existing text message flow.
- The local transcription model (~300 MB) is downloaded on first use and cached permanently; the user accepts this one-time cost.
- Ollama must be installed and running locally when selected as the AI provider; BrainSync does not manage the Ollama process lifecycle.
- For Anthropic image support, the existing configured model must be vision-capable (e.g., `claude-sonnet-4-6`); no model change is required for the default setup.
- For Ollama image support, the user must set `ai.ollama_vision_model` in `config.yaml` to a vision-capable model name (e.g., `llava`); if omitted, photo messages fall back to caption-only processing. The system does not auto-detect model capabilities.
- Video messages (including circular video notes) are out of scope due to the complexity of audio track extraction.
- Stickers, GIFs, contacts, and audio documents (`.mp3`, `.wav`) are out of scope.
- Multi-page PDF text extraction is performed locally; scanned-image PDFs are not OCR'd (out of scope).
- The maximum voice duration and PDF page limit are configurable values in `config.yaml`.
- Notes continue to be written in Ukrainian; code, configuration, and AI instructions remain in English.
- This feature targets the same single-user setup as v1.0.

---

## Out of Scope (v1.1)

- Video messages and circular video notes (requires audio extraction pipeline)
- OCR for scanned PDF documents
- Audio files sent as Telegram documents (`.mp3`, `.wav`, etc.)
- Auto-detection of Ollama model vision capability
- Stickers, GIFs, contacts, polls
