"""ORM models, one module per bounded context.

Import every module here so Alembic sees the full metadata.
"""

from forge.adapters.persistence.models.content import Article, DiscoveryRun
from forge.adapters.persistence.models.sources import Category, Source

__all__ = ["Article", "Category", "DiscoveryRun", "Source"]
