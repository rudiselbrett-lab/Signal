"""LLM quality assessment: the judged inputs to the deterministic score."""

from pydantic import BaseModel, Field

from forge.domain.scoring import Difficulty

ASSESS_SYSTEM = """\
You assess articles for a professional learning platform. Judge only what is
in the text. Be strict: marketing fluff, rehashed news, and listicles score
low on practicality and evidence quality; primary sources, data, worked
examples, and hard-won experience score high. Keep rationales to one short
sentence each."""

ASSESS_USER_TEMPLATE = """\
Assess this article.

Title: {title}
Author: {author}
Source type: {source_type}

Article text (may be truncated):
{text}"""

ASSESS_PROMPT_VERSION = "assess.v1"
MAX_ASSESS_CHARS = 24_000  # plenty of signal; keeps pipeline calls cheap


class QualityAssessment(BaseModel):
    """Structured output of the assessment call."""

    evidence_quality: float = Field(
        ge=0, le=1, description="Rigor of evidence: data, primary experience, citations"
    )
    evidence_rationale: str
    practicality: float = Field(
        ge=0, le=1, description="Actionable takeaways a professional can apply"
    )
    practicality_rationale: str
    knowledge_gap_estimate: float = Field(
        ge=0, le=1, description="How specialized/underexposed this knowledge typically is"
    )
    knowledge_gap_rationale: str
    difficulty: Difficulty
    topics: list[str] = Field(
        max_length=6, description="3-6 lowercase kebab-case topics, e.g. 'api-gateways'"
    )


def build_assess_user(title: str, author: str | None, source_type: str, text: str) -> str:
    return ASSESS_USER_TEMPLATE.format(
        title=title,
        author=author or "unknown",
        source_type=source_type,
        text=text[:MAX_ASSESS_CHARS],
    )
