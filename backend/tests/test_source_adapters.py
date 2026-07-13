from forge.adapters.sources.hackernews import parse_hits
from forge.adapters.sources.reddit import parse_listing

HN_HITS = [
    {
        "objectID": "411",
        "title": "Show HN: Forge",
        "url": "https://example.com/forge",
        "author": "ada",
        "points": 250,
        "num_comments": 42,
        "created_at_i": 1780000000,
    },
    {
        "objectID": "412",
        "title": "Low-signal post",
        "url": "https://example.com/low",
        "points": 3,
        "created_at_i": 1780000001,
    },
    {
        "objectID": "413",
        "title": "Ask HN: text post",
        "url": None,
        "author": "bob",
        "points": 120,
        "created_at_i": 1780000002,
    },
]


def test_hn_parse_filters_by_points_and_handles_text_posts():
    items = parse_hits(HN_HITS, min_points=50)
    assert [i.external_id for i in items] == ["411", "413"]
    assert items[0].metadata["points"] == 250
    # Text posts fall back to the HN discussion page.
    assert items[1].url == "https://news.ycombinator.com/item?id=413"


REDDIT_CHILDREN = [
    {
        "data": {
            "name": "t3_a",
            "title": "Great paper",
            "url": "https://example.com/paper",
            "author": "carol",
            "score": 120,
            "permalink": "/r/ml/comments/a/great_paper/",
            "created_utc": 1780000000,
            "is_self": False,
        }
    },
    {
        "data": {
            "name": "t3_b",
            "title": "Self post",
            "author": "dan",
            "score": 90,
            "permalink": "/r/ml/comments/b/self_post/",
            "created_utc": 1780000001,
            "is_self": True,
            "selftext": "Discussion body",
        }
    },
    {"data": {"name": "t3_c", "title": "Low score", "score": 2}},
    {"data": {"name": "t3_d", "title": "Sticky", "score": 500, "stickied": True}},
]


def test_reddit_parse_filters_and_uses_permalink_for_self_posts():
    items = parse_listing(REDDIT_CHILDREN, min_score=20)
    assert [i.external_id for i in items] == ["t3_a", "t3_b"]
    assert items[0].url == "https://example.com/paper"
    assert items[1].url == "https://www.reddit.com/r/ml/comments/b/self_post/"
    assert items[1].summary == "Discussion body"
