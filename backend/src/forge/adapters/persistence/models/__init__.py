"""ORM models, one module per bounded context.

Import every module here so Alembic sees the full metadata.
"""

from forge.adapters.persistence.models.content import Article, DiscoveryRun
from forge.adapters.persistence.models.knowledge import ArticleEntity, Entity, KnowledgeCard
from forge.adapters.persistence.models.scoring import ArticleScore, LLMCall
from forge.adapters.persistence.models.sources import Category, Source

__all__ = [
    "Article",
    "ArticleEntity",
    "ArticleScore",
    "Category",
    "DiscoveryRun",
    "Entity",
    "KnowledgeCard",
    "LLMCall",
    "Source",
]
