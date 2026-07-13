"""Spaced-repetition scheduler: SM-2 seeded with the product ladder.

Pure functions only — trivially unit-testable, replaceable by FSRS later
without touching anything else.

The base ladder (1, 3, 7, 14, 30, 90 days) drives early repetitions, scaled
by the item's personalized ease factor; beyond the ladder, classic SM-2
multiplicative growth takes over. Failures reset to day 1 and count a lapse;
an item lapsing MAX_LAPSES times is suspended and surfaced as a weak-area
signal instead of nagging forever.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

BASE_LADDER = (1.0, 3.0, 7.0, 14.0, 30.0, 90.0)
DEFAULT_EASE = 2.5
MIN_EASE = 1.3
MAX_LAPSES = 8
FUZZ_RATIO = 0.10  # ±10% interval jitter to avoid review pile-ups

PASS_THRESHOLD = 3  # SM-2 grade ∈ [0,5]; ≥3 is a pass


@dataclass(frozen=True)
class CardState:
    ease_factor: float = DEFAULT_EASE
    interval_days: float = 0.0
    repetitions: int = 0
    lapses: int = 0


@dataclass(frozen=True)
class ReviewOutcome:
    state: CardState
    due_at: datetime
    suspended: bool


def _updated_ease(ease: float, grade: int) -> float:
    q = grade
    return max(MIN_EASE, ease + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))


def review(
    state: CardState,
    grade: int,
    now: datetime,
    fuzz: float = 0.0,
) -> ReviewOutcome:
    """Apply one review result. `fuzz` ∈ [-FUZZ_RATIO, FUZZ_RATIO] is injected
    by the caller (deterministic in tests, random in production)."""
    if not 0 <= grade <= 5:
        raise ValueError(f"grade must be 0-5, got {grade}")
    if not -FUZZ_RATIO <= fuzz <= FUZZ_RATIO:
        raise ValueError(f"fuzz out of range: {fuzz}")

    if grade < PASS_THRESHOLD:
        lapses = state.lapses + 1
        new_state = CardState(
            ease_factor=max(MIN_EASE, state.ease_factor - 0.2),
            interval_days=1.0,
            repetitions=0,
            lapses=lapses,
        )
        return ReviewOutcome(
            state=new_state,
            due_at=now + timedelta(days=1),
            suspended=lapses >= MAX_LAPSES,
        )

    ease = _updated_ease(state.ease_factor, grade)
    repetitions = state.repetitions + 1
    if repetitions <= len(BASE_LADDER):
        interval = BASE_LADDER[repetitions - 1] * (ease / DEFAULT_EASE)
    else:
        interval = state.interval_days * ease
    interval = max(1.0, interval * (1 + fuzz))

    new_state = CardState(
        ease_factor=ease,
        interval_days=interval,
        repetitions=repetitions,
        lapses=state.lapses,
    )
    return ReviewOutcome(
        state=new_state,
        due_at=now + timedelta(days=interval),
        suspended=False,
    )


MASTERY_INTERVAL_DAYS = 30.0
MASTERY_STREAK = 2


def is_item_mastered(state: CardState, consecutive_correct: int) -> bool:
    return state.interval_days >= MASTERY_INTERVAL_DAYS and consecutive_correct >= MASTERY_STREAK
