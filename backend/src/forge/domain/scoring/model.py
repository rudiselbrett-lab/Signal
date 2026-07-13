"""Scoring domain: deterministic, explainable score arithmetic.

The LLM assesses qualities (credibility of evidence, practicality,
difficulty); embeddings provide similarity signals. This module owns the
weights and the math, so scores are stable, tunable, and every component
carries a human-readable rationale.

Component maxima (sum = 100):
  relevance 30 · novelty 20 · credibility 20 · practicality 15 ·
  knowledge gap 10 · reading-time bonus 5

Note: the product spec's example maxima (30/20/20/15/15/5) sum to 105; we
trim knowledge gap to 10 so "components sum to the overall score" holds
exactly — the most important explainability property.
"""

from dataclasses import dataclass
from enum import StrEnum

SCORING_VERSION = "v1"

MAX_RELEVANCE = 30
MAX_NOVELTY = 20
MAX_CREDIBILITY = 20
MAX_PRACTICALITY = 15
MAX_KNOWLEDGE_GAP = 10
MAX_READING_TIME = 5


class Difficulty(StrEnum):
    INTRO = "intro"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


@dataclass(frozen=True)
class Component:
    points: int
    maximum: int
    rationale: str


@dataclass(frozen=True)
class ScoreBreakdown:
    relevance: Component
    novelty: Component
    credibility: Component
    practicality: Component
    knowledge_gap: Component
    reading_time_bonus: Component

    @property
    def overall(self) -> int:
        return (
            self.relevance.points
            + self.novelty.points
            + self.credibility.points
            + self.practicality.points
            + self.knowledge_gap.points
            + self.reading_time_bonus.points
        )


def _clamp(value: float, maximum: int) -> int:
    return max(0, min(maximum, round(value)))


def score_relevance(
    interest_similarity: float | None,
    source_weight: float,
    category_weight: float,
) -> Component:
    """interest_similarity is cosine ∈ [0,1] against the user's interest
    embedding; None until an interest profile exists (cold start → neutral)."""
    weight = max(0.5, min(1.5, (source_weight * category_weight) ** 0.5))
    if interest_similarity is None:
        points = _clamp(MAX_RELEVANCE * 0.7 * weight, MAX_RELEVANCE)
        return Component(points, MAX_RELEVANCE, "No interest profile yet; neutral prior")
    points = _clamp(MAX_RELEVANCE * interest_similarity * weight, MAX_RELEVANCE)
    return Component(
        points,
        MAX_RELEVANCE,
        f"Interest match {interest_similarity:.0%}, source weight x{weight:.2f}",
    )


def score_novelty(max_library_similarity: float | None) -> Component:
    """How much of this is new ground vs. the existing library."""
    if max_library_similarity is None:
        return Component(
            _clamp(MAX_NOVELTY * 0.7, MAX_NOVELTY), MAX_NOVELTY, "Library too small to compare"
        )
    novelty = 1.0 - max_library_similarity
    return Component(
        _clamp(MAX_NOVELTY * novelty, MAX_NOVELTY),
        MAX_NOVELTY,
        f"{novelty:.0%} distinct from the closest article you've saved",
    )


# Base credibility rates by source type: primary/curated sources start higher.
SOURCE_TYPE_CREDIBILITY = {
    "arxiv": 0.85,
    "github": 0.75,
    "rss": 0.70,
    "hackernews": 0.60,
    "youtube": 0.55,
    "reddit": 0.50,
    "custom_url": 0.60,
}


def score_credibility(source_type: str, llm_evidence_quality: float, rationale: str) -> Component:
    """Blend of source-type base rate (40%) and LLM-assessed evidence quality (60%)."""
    base = SOURCE_TYPE_CREDIBILITY.get(source_type, 0.6)
    blended = 0.4 * base + 0.6 * llm_evidence_quality
    return Component(_clamp(MAX_CREDIBILITY * blended, MAX_CREDIBILITY), MAX_CREDIBILITY, rationale)


def score_practicality(llm_practicality: float, rationale: str) -> Component:
    return Component(
        _clamp(MAX_PRACTICALITY * llm_practicality, MAX_PRACTICALITY), MAX_PRACTICALITY, rationale
    )


def score_knowledge_gap(
    gap_alignment: float | None, llm_gap_estimate: float, rationale: str
) -> Component:
    """gap_alignment: overlap with high-interest/low-mastery topics (None until
    mastery data exists) — when present it dominates the LLM's estimate."""
    value = (
        llm_gap_estimate if gap_alignment is None else 0.3 * llm_gap_estimate + 0.7 * gap_alignment
    )
    return Component(
        _clamp(MAX_KNOWLEDGE_GAP * value, MAX_KNOWLEDGE_GAP), MAX_KNOWLEDGE_GAP, rationale
    )


def score_reading_time(reading_time_minutes: int) -> Component:
    """Bonus for reads that fit a focused session; long reads aren't penalized,
    they just don't get the bonus."""
    if 3 <= reading_time_minutes <= 25:
        return Component(
            MAX_READING_TIME, MAX_READING_TIME, f"{reading_time_minutes} min fits a focused session"
        )
    if reading_time_minutes < 3:
        return Component(2, MAX_READING_TIME, "Very short; likely shallow coverage")
    return Component(3, MAX_READING_TIME, f"Long read ({reading_time_minutes} min); plan for it")
