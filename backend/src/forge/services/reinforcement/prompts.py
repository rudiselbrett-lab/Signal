"""Reinforcement prompts: item generation and open-ended grading."""

from pydantic import BaseModel, Field

from forge.adapters.persistence.models.reinforcement import CardType

GENERATE_PROMPT_VERSION = "reviews.generate.v1"
GENERATE_SYSTEM = """\
You create spaced-repetition review items from an article's knowledge card.
Rules:
- Every item must be answerable from the key ideas provided — never require
  outside knowledge, and anchor each item to the key idea it tests.
- Mix card types: quick_recall (short factual), multiple_choice (4 options,
  exactly one correct, plausible distractors), scenario (apply the idea to a
  realistic situation), compare (contrast two concepts from the card), and
  explain (explain in your own words).
- expected_points are the 2-4 things a good answer must contain; graders see
  only these, so make them self-contained.
- Write questions a busy professional respects: specific, no trivia."""

GENERATE_USER_TEMPLATE = """\
Create {count} review items for this article.

Title: {title}

Summary: {summary}

Key ideas:
{key_ideas}

Mental models: {mental_models}
Frameworks: {frameworks}"""

GRADE_PROMPT_VERSION = "reviews.grade.v1"
GRADE_SYSTEM = """\
You grade a learner's answer to a review question on the SM-2 scale:
5 = perfect recall, 4 = correct with minor gaps, 3 = correct but effortful or
partially incomplete, 2 = wrong but on the right track, 1 = wrong with a
fragment of recall, 0 = blank/unrelated.
Grade ONLY against the expected points. Feedback: one or two sentences,
start with what was right, then the most important thing missed."""

GRADE_USER_TEMPLATE = """\
Question: {question}

Expected points a good answer must contain:
{expected_points}

Learner's answer:
{answer}"""


class GeneratedItem(BaseModel):
    card_type: CardType
    question: str
    options: list[str] | None = Field(
        default=None, description="Exactly 4 options; multiple_choice only"
    )
    correct_option: int | None = Field(
        default=None, ge=0, le=3, description="Index of the correct option; multiple_choice only"
    )
    expected_points: list[str] = Field(min_length=1, max_length=4)
    anchor: str = Field(description="The key idea this item tests, verbatim from the card")


class GeneratedItems(BaseModel):
    items: list[GeneratedItem] = Field(min_length=3, max_length=6)


class GradeResult(BaseModel):
    grade: int = Field(ge=0, le=5)
    feedback: str


def build_generate_user(
    title: str,
    summary: str,
    key_ideas: list[dict[str, str]],
    mental_models: list[str],
    frameworks: list[str],
    count: int = 4,
) -> str:
    ideas = "\n".join(
        f'- {ki.get("idea", "")} (quote: "{ki.get("quote", "")}")' for ki in key_ideas
    )
    return GENERATE_USER_TEMPLATE.format(
        count=count,
        title=title,
        summary=summary,
        key_ideas=ideas,
        mental_models=", ".join(mental_models) or "none",
        frameworks=", ".join(frameworks) or "none",
    )


def build_grade_user(question: str, expected_points: list[str], answer: str) -> str:
    return GRADE_USER_TEMPLATE.format(
        question=question,
        expected_points="\n".join(f"- {p}" for p in expected_points),
        answer=answer,
    )
