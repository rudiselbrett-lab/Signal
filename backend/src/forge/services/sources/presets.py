"""Curated one-click sources shown in the 'Add source' UI."""

from forge.domain.sources import SourceType
from forge.services.sources.schemas import SourcePreset

PRESETS: list[SourcePreset] = [
    SourcePreset(
        name="Anthropic News",
        source_type=SourceType.RSS,
        config={"feed_url": "https://www.anthropic.com/rss.xml"},
        description="Research and product announcements from Anthropic",
    ),
    SourcePreset(
        name="OpenAI Blog",
        source_type=SourceType.RSS,
        config={"feed_url": "https://openai.com/blog/rss.xml"},
        description="Research and product announcements from OpenAI",
    ),
    SourcePreset(
        name="Stripe Engineering",
        source_type=SourceType.RSS,
        config={"feed_url": "https://stripe.com/blog/engineering/feed.rss"},
        description="Engineering deep dives from Stripe",
    ),
    SourcePreset(
        name="Netflix Tech Blog",
        source_type=SourceType.RSS,
        config={"feed_url": "https://netflixtechblog.com/feed"},
        description="Architecture and infrastructure at Netflix scale",
    ),
    SourcePreset(
        name="Hacker News (best)",
        source_type=SourceType.HACKERNEWS,
        config={"feed": "best", "min_points": 100},
        description="Highest-signal stories from Hacker News",
    ),
    SourcePreset(
        name="arXiv: AI agents",
        source_type=SourceType.ARXIV,
        config={"query": "cat:cs.AI AND abs:agents", "max_results": 20},
        description="New arXiv papers about AI agents",
    ),
    SourcePreset(
        name="r/MachineLearning",
        source_type=SourceType.REDDIT,
        config={"subreddit": "MachineLearning", "min_score": 50},
        description="Top posts from r/MachineLearning",
    ),
]
