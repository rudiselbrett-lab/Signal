"""Source adapters. Importing this package registers all built-in adapters."""

from forge.adapters.sources.base import get_adapter, register_adapter, registered_types
from forge.adapters.sources.custom_url import CustomURLAdapter
from forge.adapters.sources.rss import RSSAdapter

register_adapter(RSSAdapter())
register_adapter(CustomURLAdapter())

__all__ = ["get_adapter", "register_adapter", "registered_types"]
