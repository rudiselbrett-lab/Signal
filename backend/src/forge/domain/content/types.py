"""Content domain: article lifecycle and normalization helpers."""

import hashlib
import math
import re
from enum import StrEnum
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


class ArticleStatus(StrEnum):
    DISCOVERED = "discovered"  # found by a source, not yet scored
    SUGGESTED = "suggested"  # scored, surfaced in Today's Reading
    UNREAD = "unread"  # saved to the library
    READING = "reading"
    LEARNED = "learned"  # read; reinforcement generated
    REVIEW_DUE = "review_due"  # ≥1 review item due (owned by Reinforcement)
    MASTERED = "mastered"  # all items at long intervals, no recent lapses
    DISMISSED = "dismissed"
    ARCHIVED = "archived"


# Statuses that mean "this article is in the user's library".
LIBRARY_STATUSES = frozenset(
    {
        ArticleStatus.UNREAD,
        ArticleStatus.READING,
        ArticleStatus.LEARNED,
        ArticleStatus.REVIEW_DUE,
        ArticleStatus.MASTERED,
    }
)


class EnrichmentStatus(StrEnum):
    PENDING = "pending"
    FETCHED = "fetched"  # full text present, knowledge extraction not yet done
    ENRICHED = "enriched"
    FAILED = "failed"


_TRACKING_PARAMS = re.compile(r"^(utm_\w+|fbclid|gclid|ref|source|mc_cid|mc_eid)$", re.IGNORECASE)

WORDS_PER_MINUTE = 225


def canonicalize_url(url: str) -> str:
    """Normalize a URL for dedupe: strip tracking params, fragment, default ports."""
    parsed = urlparse(url.strip())
    netloc = parsed.netloc.lower()
    netloc = netloc.removesuffix(":80") if parsed.scheme == "http" else netloc.removesuffix(":443")
    query = urlencode([(k, v) for k, v in parse_qsl(parsed.query) if not _TRACKING_PARAMS.match(k)])
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), netloc, path, "", query, ""))


def content_fingerprint(text: str) -> str:
    """Stable hash of normalized text for exact-duplicate detection across sources."""
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()


def estimate_reading_time(word_count: int) -> int:
    return max(1, math.ceil(word_count / WORDS_PER_MINUTE))
