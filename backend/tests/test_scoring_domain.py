from forge.domain.scoring import (
    score_credibility,
    score_knowledge_gap,
    score_novelty,
    score_practicality,
    score_reading_time,
    score_relevance,
)


def test_component_maxima_sum_to_100():
    components = [
        score_relevance(1.0, 1.5, 1.5),
        score_novelty(0.0),
        score_credibility("arxiv", 1.0, ""),
        score_practicality(1.0, ""),
        score_knowledge_gap(1.0, 1.0, ""),
        score_reading_time(10),
    ]
    assert sum(c.maximum for c in components) == 100
    assert sum(c.points for c in components) <= 100
    assert all(0 <= c.points <= c.maximum for c in components)


def test_cold_start_uses_neutral_priors():
    relevance = score_relevance(None, 1.0, 1.0)
    assert relevance.points == 21  # 70% of 30
    assert "No interest profile" in relevance.rationale
    novelty = score_novelty(None)
    assert novelty.points == 14  # 70% of 20


def test_relevance_scales_with_source_weight():
    low = score_relevance(0.8, 0.5, 1.0)
    high = score_relevance(0.8, 1.5, 1.5)
    assert high.points > low.points
    assert 0 <= low.points <= 30


def test_novelty_penalizes_near_duplicates():
    assert score_novelty(0.95).points == 1
    assert score_novelty(0.10).points == 18


def test_credibility_blends_source_base_and_evidence():
    arxiv_weak = score_credibility("arxiv", 0.2, "thin evidence")
    reddit_strong = score_credibility("reddit", 0.9, "primary data")
    assert arxiv_weak.points == round(20 * (0.4 * 0.85 + 0.6 * 0.2))
    assert reddit_strong.points == round(20 * (0.4 * 0.50 + 0.6 * 0.9))


def test_knowledge_gap_prefers_mastery_signal_when_available():
    llm_only = score_knowledge_gap(None, 0.8, "")
    with_mastery = score_knowledge_gap(0.2, 0.8, "")
    assert llm_only.points == 8
    assert with_mastery.points == round(10 * (0.3 * 0.8 + 0.7 * 0.2))


def test_reading_time_bonus_windows():
    assert score_reading_time(10).points == 5
    assert score_reading_time(1).points == 2
    assert score_reading_time(60).points == 3
