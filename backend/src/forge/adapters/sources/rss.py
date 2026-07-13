"""RSS/Atom adapter — covers Substack, company engineering blogs, any feed."""

import time
from datetime import UTC, datetime
from typing import Any, ClassVar

import feedparser

from forge.adapters.http import ensure_public_url, make_client
from forge.adapters.persistence.models.sources import Source
from forge.domain.sources import RawItem, SourceType


def _entry_published(entry: Any) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            return datetime.fromtimestamp(time.mktime(parsed), tz=UTC)
    return None


def parse_feed(content: bytes, since: datetime | None) -> list[RawItem]:
    """Pure parse step, separated from I/O for testability."""
    feed = feedparser.parse(content)
    items: list[RawItem] = []
    for entry in feed.entries:
        url = getattr(entry, "link", None)
        title = getattr(entry, "title", None)
        if not url or not title:
            continue
        published = _entry_published(entry)
        if since is not None and published is not None and published <= since:
            continue
        items.append(
            RawItem(
                external_id=getattr(entry, "id", url),
                url=url,
                title=title,
                author=getattr(entry, "author", None),
                published_at=published,
                summary=getattr(entry, "summary", None),
            )
        )
    return items


class RSSAdapter:
    source_type: ClassVar[SourceType] = SourceType.RSS

    async def fetch_new_items(self, source: Source, since: datetime | None) -> list[RawItem]:
        feed_url = source.config["feed_url"]
        ensure_public_url(feed_url)
        async with make_client() as client:
            resp = await client.get(feed_url)
            resp.raise_for_status()
        return parse_feed(resp.content, since)
