"""Full-content fetching: URL → clean article text + metadata.

trafilatura handles the messy 95% of the web; adapters that already have
structured content (arXiv abstracts, HN text posts) pre-fill RawItem.summary
and this step enriches or falls back gracefully.
"""

import contextlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import trafilatura

from forge.adapters.http import ensure_public_url, make_client


@dataclass(frozen=True)
class FetchedContent:
    text: str
    title: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    language: str | None = None


class ContentFetchError(Exception):
    pass


def extract_content(html: str, url: str) -> FetchedContent:
    """Pure extraction step, separated from I/O for testability."""
    raw = trafilatura.bare_extraction(html, url=url, with_metadata=True)
    doc: dict[str, Any] = raw if isinstance(raw, dict) else raw.as_dict() if raw else {}
    text = (doc.get("text") or "").strip()
    if not text:
        raise ContentFetchError(f"no extractable content at {url}")
    published_at = None
    if doc.get("date"):
        with contextlib.suppress(ValueError):
            published_at = datetime.fromisoformat(doc["date"]).replace(tzinfo=UTC)
    return FetchedContent(
        text=text,
        title=doc.get("title") or None,
        author=doc.get("author") or None,
        published_at=published_at,
        language=doc.get("language") or None,
    )


async def fetch_content(url: str) -> FetchedContent:
    ensure_public_url(url)
    async with make_client() as client:
        resp = await client.get(url)
        resp.raise_for_status()
    content_type = resp.headers.get("content-type", "")
    if "html" not in content_type and "xml" not in content_type and "text" not in content_type:
        raise ContentFetchError(f"unsupported content type {content_type!r} at {url}")
    return extract_content(resp.text, url)
