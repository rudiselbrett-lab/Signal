"""Reddit adapter via the public JSON API (no auth; requires honest UA)."""

from datetime import UTC, datetime
from typing import Any, ClassVar

from forge.adapters.http import make_client
from forge.adapters.persistence.models.sources import Source
from forge.domain.sources import RawItem, SourceType


def parse_listing(children: list[dict[str, Any]], min_score: int) -> list[RawItem]:
    items: list[RawItem] = []
    for child in children:
        post = child.get("data", {})
        title = post.get("title")
        name = post.get("name")  # t3_xxxxx
        score = post.get("score", 0)
        if not title or not name or score < min_score or post.get("stickied"):
            continue
        permalink = f"https://www.reddit.com{post.get('permalink', '')}"
        is_self = bool(post.get("is_self"))
        items.append(
            RawItem(
                external_id=name,
                url=permalink if is_self else (post.get("url") or permalink),
                title=title,
                author=post.get("author"),
                published_at=(
                    datetime.fromtimestamp(post["created_utc"], tz=UTC)
                    if post.get("created_utc")
                    else None
                ),
                summary=post.get("selftext") or None,
                metadata={"score": score, "comments_url": permalink},
            )
        )
    return items


class RedditAdapter:
    source_type: ClassVar[SourceType] = SourceType.REDDIT

    async def fetch_new_items(self, source: Source, since: datetime | None) -> list[RawItem]:
        subreddit = source.config["subreddit"]
        min_score = int(source.config.get("min_score", 20))
        url = f"https://www.reddit.com/r/{subreddit}/top.json"
        async with make_client() as client:
            resp = await client.get(url, params={"t": "day", "limit": "25", "raw_json": "1"})
            resp.raise_for_status()
        children = resp.json().get("data", {}).get("children", [])
        items = parse_listing(children, min_score)
        if since is not None:
            items = [i for i in items if i.published_at is None or i.published_at > since]
        return items
