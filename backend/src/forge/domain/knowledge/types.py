"""Knowledge domain: entities and normalization."""

import re
from enum import StrEnum


class EntityKind(StrEnum):
    TOPIC = "topic"
    COMPANY = "company"
    PRODUCT = "product"
    FRAMEWORK = "framework"
    CONCEPT = "concept"
    MENTAL_MODEL = "mental_model"


def normalize_entity_name(name: str) -> str:
    """Canonical form for entity dedupe: lowercase, single spaces, no punctuation noise."""
    cleaned = re.sub(r"[^\w\s-]", "", name.strip().lower())
    return re.sub(r"[\s_-]+", " ", cleaned).strip()
