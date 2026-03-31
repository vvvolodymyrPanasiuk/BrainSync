"""PDF text extraction using pypdf."""
from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO


@dataclass
class ExtractedDocument:
    full_text: str
    ai_context: str
    pages_extracted: int
    truncated: bool
    source_filename: str
    error: bool = False


def extract(
    file_bytes: bytes,
    max_pages: int = 50,
    ai_context_chars: int = 3000,
    source_filename: str = "",
) -> ExtractedDocument:
    """Extract text from PDF bytes. Returns ExtractedDocument."""
    try:
        from pypdf import PdfReader
        import pypdf.errors

        reader = PdfReader(BytesIO(file_bytes))
        total_pages = len(reader.pages)
        pages_to_read = min(total_pages, max_pages)
        truncated = total_pages > max_pages

        parts: list[str] = []
        for page in reader.pages[:pages_to_read]:
            text = page.extract_text()
            if text:
                parts.append(text)

        full_text = "\n\n".join(parts)
        return ExtractedDocument(
            full_text=full_text,
            ai_context=full_text[:ai_context_chars],
            pages_extracted=pages_to_read,
            truncated=truncated,
            source_filename=source_filename,
        )
    except Exception:
        return ExtractedDocument(
            full_text="",
            ai_context="",
            pages_extracted=0,
            truncated=False,
            source_filename=source_filename,
            error=True,
        )
