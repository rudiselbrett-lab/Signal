from datetime import UTC, datetime

from forge.adapters.sources.rss import parse_feed

FEED = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Example Engineering</title>
  <item>
    <title>Scaling the API gateway</title>
    <link>https://example.com/scaling-api-gateway</link>
    <guid>post-1</guid>
    <author>ada@example.com</author>
    <pubDate>Wed, 08 Jul 2026 10:00:00 GMT</pubDate>
    <description>How we scaled.</description>
  </item>
  <item>
    <title>Old post</title>
    <link>https://example.com/old</link>
    <guid>post-0</guid>
    <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
  </item>
</channel></rss>
"""


def test_parse_feed_extracts_items():
    items = parse_feed(FEED, since=None)
    assert len(items) == 2
    first = items[0]
    assert first.external_id == "post-1"
    assert first.url == "https://example.com/scaling-api-gateway"
    assert first.title == "Scaling the API gateway"
    assert first.published_at is not None


def test_parse_feed_filters_by_since():
    since = datetime(2026, 1, 1, tzinfo=UTC)
    items = parse_feed(FEED, since=since)
    assert [i.external_id for i in items] == ["post-1"]


def test_registry_has_builtin_adapters():
    from forge.adapters.sources import registered_types
    from forge.domain.sources import SourceType

    assert {SourceType.RSS, SourceType.CUSTOM_URL} <= registered_types()
