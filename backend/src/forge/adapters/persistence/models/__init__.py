"""ORM models, one module per bounded context.

Import every module here so Alembic sees the full metadata.
"""

from forge.adapters.persistence.models.content import Article, DiscoveryRun
from forge.adapters.persistence.models.knowledge import ArticleEntity, Entity, KnowledgeCard
from forge.adapters.persistence.models.reinforcement import (
    ReviewAttempt,
    ReviewItem,
    ReviewSession,
)
from forge.adapters.persistence.models.scoring import ArticleScore, LLMCall
from forge.adapters.persistence.models.search import ArticleChunk
from forge.adapters.persistence.models.sources import Category, Source

__all__ = [
    "Article",
    "ArticleChunk",
    "ArticleEntity",
    "ArticleScore",
    "Category",
    "DiscoveryRun",
    "Entity",
    "KnowledgeCard",
    "LLMCall",
    "ReviewAttempt",
    "ReviewItem",
    "ReviewSession",
    "Source",
]
