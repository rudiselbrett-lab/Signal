"""Hacker News adapter, via the Algolia HN Search API (no auth, generous limits).

feed="top"  → current front page
feed="best" → recent stories above the configured points threshold
"""

from datetime import UTC, datetime
from typing import Any, ClassVar

from forge.adapters.http import make_client
from forge.adapters.persistence.models.sources import Source
from forge.domain.sources import RawItem, SourceType

ALGOLIA_URL = "https://hn.algolia.com/api/v1"


def parse_hits(hits: list[dict[str, Any]], min_points: int) -> list[RawItem]:
    items: list[RawItem] = []
    for hit in hits:
        points = hit.get("points") or 0
        title = hit.get("title")
        object_id = hit.get("objectID")
        if not title or not object_id or points < min_points:
            continue
        hn_url = f"https://news.ycombinator.com/item?id={object_id}"
        items.append(
            RawItem(
                external_id=str(object_id),
                url=hit.get("url") or hn_url,  # text posts live on HN itself
                title=title,
                author=hit.get("author"),
                published_at=(
                    datetime.fromtimestamp(hit["created_at_i"], tz=UTC)
                    if hit.get("created_at_i")
                    else None
                ),
                metadata={
                    "points": points,
                    "num_comments": hit.get("num_comments", 0),
                    "comments_url": hn_url,
                },
            )
        )
    return items


class HackerNewsAdapter:
    source_type: ClassVar[SourceType] = SourceType.HACKERNEWS

    async def fetch_new_items(self, source: Source, since: datetime | None) -> list[RawItem]:
        feed = source.config.get("feed", "best")
        min_points = int(source.config.get("min_points", 50))
        if feed == "top":
            params: dict[str, Any] = {"tags": "front_page", "hitsPerPage": 30}
            endpoint = f"{ALGOLIA_URL}/search"
        else:
            params = {
                "tags": "story",
                "numericFilters": f"points>={min_points}",
                "hitsPerPage": 30,
            }
            if since is not None:
                params["numericFilters"] += f",created_at_i>{int(since.timestamp())}"
            endpoint = f"{ALGOLIA_URL}/search_by_date"
        async with make_client() as client:
            resp = await client.get(endpoint, params=params)
            resp.raise_for_status()
        return parse_hits(resp.json().get("hits", []), min_points)
