"""Custom URL adapter: a single page the user wants ingested.

Emits the page as one item; ingestion's dedupe layer makes repeat discovery
runs a no-op unless the page was never successfully ingested.
"""

from datetime import datetime
from typing import ClassVar

from forge.adapters.http import ensure_public_url
from forge.adapters.persistence.models.sources import Source
from forge.domain.sources import RawItem, SourceType


class CustomURLAdapter:
    source_type: ClassVar[SourceType] = SourceType.CUSTOM_URL

    async def fetch_new_items(self, source: Source, since: datetime | None) -> list[RawItem]:
        url = source.config["url"]
        ensure_public_url(url)
        # Title/author/text are resolved by the content fetch step.
        return [RawItem(external_id=url, url=url, title=source.name)]
