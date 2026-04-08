"""Web clipper: fetch a URL, strip HTML, return (title, text) for note creation."""
from __future__ import annotations

import re
import urllib.request
from html.parser import HTMLParser


_SKIP_TAGS = frozenset({"script", "style", "nav", "footer", "header", "aside", "noscript"})
_MAX_FETCH_BYTES = 512 * 1024   # 512 KB — enough for any article


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in _SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            chunk = data.strip()
            if chunk:
                self.chunks.append(chunk)


def fetch_url(url: str, max_chars: int = 5000) -> tuple[str, str]:
    """Fetch *url* and return *(page_title, extracted_text)*.

    Raises ``urllib.error.URLError`` / ``ValueError`` on network or parse failures.
    The caller is responsible for catching these.
    """
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; BrainSync/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read(_MAX_FETCH_BYTES)
        charset = resp.headers.get_content_charset("utf-8") or "utf-8"

    html = raw.decode(charset, errors="replace")

    title_m = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
    title = re.sub(r'\s+', ' ', title_m.group(1)).strip() if title_m else url

    parser = _TextExtractor()
    parser.feed(html)
    text = " ".join(parser.chunks)
    text = re.sub(r'\s+', ' ', text).strip()
    return title, text[:max_chars]
