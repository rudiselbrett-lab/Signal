import uuid

import pytest

from forge.adapters.persistence.models.content import Article
from forge.api.errors import ConflictError, NotFoundError
from forge.config import DEFAULT_USER_ID
from forge.domain.content import ArticleStatus
from forge.events import bus
from forge.services.library.service import LibraryService

USER = DEFAULT_USER_ID


class FakeLibraryRepo:
    def __init__(self, articles):
        self.articles = {a.id: a for a in articles}

    async def get_article(self, user_id, article_id):
        a = self.articles.get(article_id)
        return a if a and a.user_id == user_id else None

    async def list_articles(self, user_id, statuses, order_by_score, limit, offset):
        rows = [a for a in self.articles.values() if not statuses or a.status in statuses]
        return [(a, None, None) for a in rows[offset : offset + limit]]

    async def get_score(self, user_id, article_id):
        return None

    async def get_card(self, user_id, article_id):
        return None

    async def get_entities(self, user_id, article_id):
        return []


def make_article(status):
    return Article(
        id=uuid.uuid4(),
        user_id=USER,
        url="https://example.com/x",
        canonical_url="https://example.com/x",
        title="X",
        status=status,
    )


@pytest.fixture(autouse=True)
def clean_bus():
    bus.clear_subscribers()
    events = []
    for name in ("article.saved", "article.read", "suggestion.dismissed"):
        bus.subscribe(name, events.append)
    yield events
    bus.clear_subscribers()


async def test_save_emits_article_saved(clean_bus):
    article = make_article(ArticleStatus.SUGGESTED)
    svc = LibraryService(FakeLibraryRepo([article]))

    await svc.apply_action(USER, article.id, "save")

    assert article.status == ArticleStatus.UNREAD
    assert [e.name for e in clean_bus] == ["article.saved"]


async def test_mark_read_from_suggested_implies_save(clean_bus):
    article = make_article(ArticleStatus.SUGGESTED)
    svc = LibraryService(FakeLibraryRepo([article]))

    await svc.apply_action(USER, article.id, "mark_read")

    assert article.status == ArticleStatus.LEARNED
    assert [e.name for e in clean_bus] == ["article.saved", "article.read"]


async def test_mark_read_from_reading_emits_only_read(clean_bus):
    article = make_article(ArticleStatus.READING)
    svc = LibraryService(FakeLibraryRepo([article]))

    await svc.apply_action(USER, article.id, "mark_read")
    assert [e.name for e in clean_bus] == ["article.read"]


async def test_invalid_transition_conflicts(clean_bus):
    article = make_article(ArticleStatus.MASTERED)
    svc = LibraryService(FakeLibraryRepo([article]))

    with pytest.raises(ConflictError):
        await svc.apply_action(USER, article.id, "save")
    assert clean_bus == []


async def test_idempotent_action_emits_no_duplicate_events(clean_bus):
    article = make_article(ArticleStatus.SUGGESTED)
    svc = LibraryService(FakeLibraryRepo([article]))

    await svc.apply_action(USER, article.id, "save")
    await svc.apply_action(USER, article.id, "save")

    assert [e.name for e in clean_bus] == ["article.saved"]


async def test_unknown_article_404s(clean_bus):
    svc = LibraryService(FakeLibraryRepo([]))
    with pytest.raises(NotFoundError):
        await svc.apply_action(USER, uuid.uuid4(), "save")
