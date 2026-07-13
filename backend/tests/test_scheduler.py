from datetime import UTC, datetime, timedelta

import pytest

from forge.domain.reinforcement import (
    BASE_LADDER,
    MAX_LAPSES,
    CardState,
    is_item_mastered,
    review,
)

NOW = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)


def test_ladder_progression_at_default_ease():
    """Grade-4 answers hold EF at 2.5, so intervals follow the spec ladder."""
    state = CardState()
    intervals = []
    now = NOW
    for _ in BASE_LADDER:
        outcome = review(state, grade=4, now=now)
        intervals.append(round(outcome.state.interval_days))
        state = outcome.state
        now = outcome.due_at
    assert intervals == [1, 3, 7, 14, 30, 90]


def test_beyond_ladder_grows_multiplicatively():
    state = CardState(ease_factor=2.5, interval_days=90.0, repetitions=6)
    outcome = review(state, grade=4, now=NOW)
    assert outcome.state.interval_days == pytest.approx(90 * 2.5)


def test_grade_5_raises_ease_grade_3_lowers_it():
    up = review(CardState(), grade=5, now=NOW)
    down = review(CardState(), grade=3, now=NOW)
    assert up.state.ease_factor > 2.5
    assert down.state.ease_factor < 2.5
    assert down.state.ease_factor >= 1.3


def test_struggling_item_gets_shorter_ladder_intervals():
    """A lower ease factor scales the ladder down for that item."""
    state = CardState(ease_factor=1.5, interval_days=3.0, repetitions=2)
    outcome = review(state, grade=3, now=NOW)
    default = review(CardState(interval_days=3.0, repetitions=2), grade=3, now=NOW)
    assert outcome.state.interval_days < default.state.interval_days


def test_failure_resets_to_day_one_and_counts_lapse():
    state = CardState(ease_factor=2.5, interval_days=30.0, repetitions=5, lapses=1)
    outcome = review(state, grade=1, now=NOW)
    assert outcome.state.repetitions == 0
    assert outcome.state.interval_days == 1.0
    assert outcome.state.lapses == 2
    assert outcome.due_at == NOW + timedelta(days=1)
    assert not outcome.suspended


def test_item_suspends_after_max_lapses():
    state = CardState(lapses=MAX_LAPSES - 1)
    outcome = review(state, grade=0, now=NOW)
    assert outcome.suspended


def test_fuzz_jitters_interval_within_bounds():
    base = review(CardState(), grade=4, now=NOW)
    plus = review(CardState(), grade=4, now=NOW, fuzz=0.1)
    minus = review(CardState(), grade=4, now=NOW, fuzz=-0.1)
    assert minus.state.interval_days <= base.state.interval_days <= plus.state.interval_days
    with pytest.raises(ValueError):
        review(CardState(), grade=4, now=NOW, fuzz=0.5)


def test_invalid_grade_rejected():
    with pytest.raises(ValueError):
        review(CardState(), grade=6, now=NOW)


def test_mastery_requires_long_interval_and_streak():
    assert is_item_mastered(CardState(interval_days=30.0), consecutive_correct=2)
    assert not is_item_mastered(CardState(interval_days=29.0), consecutive_correct=5)
    assert not is_item_mastered(CardState(interval_days=90.0), consecutive_correct=1)
