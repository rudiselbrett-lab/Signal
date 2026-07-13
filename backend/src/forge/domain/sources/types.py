"""Sources domain: source types, statuses, and per-type configuration.

A Source is "somewhere Forge looks for new things to learn". Each
source_type has a typed config schema; adapters receive validated config.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator


class SourceType(StrEnum):
    RSS = "rss"  # covers Substack, company engineering blogs, any feed
    REDDIT = "reddit"
    HACKERNEWS = "hackernews"
    GITHUB = "github"
    ARXIV = "arxiv"
    YOUTUBE = "youtube"
    CUSTOM_URL = "custom_url"


class SourceStatus(StrEnum):
    ACTIVE = "active"
    ERRORING = "erroring"
    DISABLED = "disabled"


# --- per-type config schemas -------------------------------------------------


class RSSConfig(BaseModel):
    feed_url: HttpUrl


class RedditConfig(BaseModel):
    subreddit: str = Field(min_length=1, max_length=100)
    min_score: int = 20

    @field_validator("subreddit")
    @classmethod
    def strip_prefix(cls, v: str) -> str:
        return v.removeprefix("r/").strip("/")


class HackerNewsConfig(BaseModel):
    feed: str = Field(default="best", pattern="^(top|best)$")
    min_points: int = 50


class GitHubConfig(BaseModel):
    repo: str = Field(pattern=r"^[\w.-]+/[\w.-]+$")  # owner/name


class ArxivConfig(BaseModel):
    query: str = Field(min_length=1, max_length=300)  # e.g. "cat:cs.AI AND abs:agents"
    max_results: int = Field(default=20, le=100)


class YouTubeConfig(BaseModel):
    channel_id: str = Field(min_length=1, max_length=100)


class CustomURLConfig(BaseModel):
    url: HttpUrl


CONFIG_SCHEMAS: dict[SourceType, type[BaseModel]] = {
    SourceType.RSS: RSSConfig,
    SourceType.REDDIT: RedditConfig,
    SourceType.HACKERNEWS: HackerNewsConfig,
    SourceType.GITHUB: GitHubConfig,
    SourceType.ARXIV: ArxivConfig,
    SourceType.YOUTUBE: YouTubeConfig,
    SourceType.CUSTOM_URL: CustomURLConfig,
}


def validate_source_config(source_type: SourceType, config: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize adapter config; raises pydantic.ValidationError."""
    return CONFIG_SCHEMAS[source_type].model_validate(config).model_dump(mode="json")


# --- what adapters produce ---------------------------------------------------


class RawItem(BaseModel):
    """A discovered item, before fetching/enrichment."""

    external_id: str  # stable id within the source (guid, HN id, arXiv id…)
    url: str
    title: str
    author: str | None = None
    published_at: datetime | None = None
    summary: str | None = None  # feed-provided teaser, if any
    metadata: dict[str, Any] = Field(default_factory=dict)  # points, comments url, …
