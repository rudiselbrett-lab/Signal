"""Knowledge extraction prompt + structured output schema."""

from pydantic import BaseModel, Field

from forge.domain.scoring import Difficulty

EXTRACT_PROMPT_VERSION = "extract.v1"
EXTRACT_SYSTEM = """\
You extract structured knowledge from articles for a personal learning
library. Every key idea must be anchored to a short verbatim quote from the
text (max 25 words) that supports it — never invent quotes. Mental models
and frameworks must be named as the article presents them. Topics are
lowercase kebab-case. Be selective: 3-6 key ideas that would matter to a
professional a year from now, not a paragraph-by-paragraph outline."""

EXTRACT_USER_TEMPLATE = """\
Extract the knowledge card for this article.

Title: {title}
Author: {author}

Article text:
{text}"""

MAX_EXTRACT_CHARS = 60_000


class KeyIdea(BaseModel):
    idea: str = Field(description="One self-contained idea, stated plainly")
    quote: str = Field(description="Short verbatim supporting quote from the article")


class NamedEntity(BaseModel):
    name: str
    kind: str = Field(description="one of: company, product, framework, concept, mental_model")


class ExtractedKnowledge(BaseModel):
    summary: str = Field(description="3-5 sentence summary a busy expert would trust")
    key_ideas: list[KeyIdea] = Field(min_length=1, max_length=6)
    mental_models: list[str] = Field(default_factory=list, max_length=5)
    frameworks: list[str] = Field(default_factory=list, max_length=5)
    entities: list[NamedEntity] = Field(default_factory=list, max_length=15)
    topics: list[str] = Field(min_length=1, max_length=6)
    tags: list[str] = Field(default_factory=list, max_length=8)
    difficulty: Difficulty


def build_extract_user(title: str, author: str | None, text: str) -> str:
    return EXTRACT_USER_TEMPLATE.format(
        title=title, author=author or "unknown", text=text[:MAX_EXTRACT_CHARS]
    )
