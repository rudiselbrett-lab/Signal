"""arXiv adapter via the export API (Atom feed, reuses the RSS parse step)."""

from datetime import datetime
from typing import ClassVar

from forge.adapters.http import make_client
from forge.adapters.persistence.models.sources import Source
from forge.adapters.sources.rss import parse_feed
from forge.domain.sources import RawItem, SourceType

EXPORT_URL = "https://export.arxiv.org/api/query"


class ArxivAdapter:
    source_type: ClassVar[SourceType] = SourceType.ARXIV

    async def fetch_new_items(self, source: Source, since: datetime | None) -> list[RawItem]:
        params = {
            "search_query": source.config["query"],
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": str(source.config.get("max_results", 20)),
        }
        async with make_client() as client:
            resp = await client.get(EXPORT_URL, params=params)
            resp.raise_for_status()
        # arXiv abstracts arrive in the feed itself; keep them as the teaser
        # so papers are useful even before PDF-level ingestion exists.
        return parse_feed(resp.content, since)
