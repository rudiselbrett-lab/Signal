"""SourceAdapter port and registry.

Adding a new source type (podcast, PDF, Readwise…) means implementing this
protocol and registering it — nothing else in the system changes.
"""

from datetime import datetime
from typing import ClassVar, Protocol, runtime_checkable

from forge.adapters.persistence.models.sources import Source
from forge.domain.sources import RawItem, SourceType


@runtime_checkable
class SourceAdapter(Protocol):
    source_type: ClassVar[SourceType]

    async def fetch_new_items(self, source: Source, since: datetime | None) -> list[RawItem]:
        """Return items published/updated after `since` (all items if None)."""
        ...


_registry: dict[SourceType, SourceAdapter] = {}


def register_adapter(adapter: SourceAdapter) -> None:
    _registry[adapter.source_type] = adapter


def get_adapter(source_type: SourceType) -> SourceAdapter:
    try:
        return _registry[source_type]
    except KeyError:
        raise LookupError(f"no adapter registered for source type {source_type!r}") from None


def registered_types() -> set[SourceType]:
    return set(_registry)
