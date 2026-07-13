"""Domain event catalog — the stable contract between bounded contexts.

Payload fields must be JSON-serializable (ids as strings) because async
subscribers receive them as Celery task kwargs.
"""

from dataclasses import dataclass, field

from forge.events.bus import DomainEvent


@dataclass(frozen=True, kw_only=True)
class ArticleDiscovered(DomainEvent):
    """Full text fetched; ready for scoring."""

    name: str = field(init=False, default="article.discovered")
    article_id: str
    user_id: str


@dataclass(frozen=True, kw_only=True)
class ArticleSaved(DomainEvent):
    """User saved the article to the library; ready for knowledge extraction."""

    name: str = field(init=False, default="article.saved")
    article_id: str
    user_id: str


@dataclass(frozen=True, kw_only=True)
class ArticleEnriched(DomainEvent):
    """Knowledge card extracted; ready for embeddings + graph."""

    name: str = field(init=False, default="article.enriched")
    article_id: str
    user_id: str


@dataclass(frozen=True, kw_only=True)
class ArticleRead(DomainEvent):
    """User finished reading; generate reinforcement, update analytics."""

    name: str = field(init=False, default="article.read")
    article_id: str
    user_id: str


@dataclass(frozen=True, kw_only=True)
class ReviewCompleted(DomainEvent):
    name: str = field(init=False, default="review.completed")
    review_item_id: str
    article_id: str
    user_id: str
    grade: int


@dataclass(frozen=True, kw_only=True)
class SuggestionDismissed(DomainEvent):
    name: str = field(init=False, default="suggestion.dismissed")
    article_id: str
    user_id: str


@dataclass(frozen=True, kw_only=True)
class ChatRetrievalMissed(DomainEvent):
    """The coach couldn't ground an answer — a knowledge-gap signal."""

    name: str = field(init=False, default="chat.retrieval_missed")
    user_id: str
    query: str
