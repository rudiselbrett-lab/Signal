import pytest

from forge.api.errors import ConflictError, NotFoundError, ValidationFailedError
from forge.config import DEFAULT_USER_ID
from forge.domain.sources import SourceStatus, SourceType
from forge.services.sources.schemas import CategoryCreate, SourceCreate, SourceUpdate
from forge.services.sources.service import SourcesService
from tests.fakes import FakeSourcesRepository

USER = DEFAULT_USER_ID


@pytest.fixture
def svc():
    return SourcesService(FakeSourcesRepository())


async def test_create_source_validates_and_normalizes_config(svc):
    source = await svc.create_source(
        USER,
        SourceCreate(
            name="Stripe Engineering",
            source_type=SourceType.RSS,
            config={"feed_url": "https://stripe.com/blog/feed.rss"},
        ),
    )
    assert source.config == {"feed_url": "https://stripe.com/blog/feed.rss"}
    assert source.enabled is True


async def test_create_source_rejects_bad_config(svc):
    with pytest.raises(ValidationFailedError):
        await svc.create_source(
            USER,
            SourceCreate(name="bad", source_type=SourceType.RSS, config={"feed_url": "not-a-url"}),
        )


async def test_reddit_config_strips_r_prefix(svc):
    source = await svc.create_source(
        USER,
        SourceCreate(
            name="ML", source_type=SourceType.REDDIT, config={"subreddit": "r/MachineLearning"}
        ),
    )
    assert source.config["subreddit"] == "MachineLearning"


async def test_update_unknown_source_raises_not_found(svc):
    import uuid

    with pytest.raises(NotFoundError):
        await svc.update_source(USER, uuid.uuid4(), SourceUpdate(name="x"))


async def test_reenabling_erroring_source_resets_error_state(svc):
    source = await svc.create_source(
        USER,
        SourceCreate(name="HN", source_type=SourceType.HACKERNEWS, config={"feed": "best"}),
    )
    source.status = SourceStatus.ERRORING
    source.failure_count = 5
    source.enabled = False

    updated = await svc.update_source(USER, source.id, SourceUpdate(enabled=True))
    assert updated.status == SourceStatus.ACTIVE
    assert updated.failure_count == 0


async def test_duplicate_category_name_conflicts(svc):
    await svc.create_category(USER, CategoryCreate(name="AI"))
    with pytest.raises(ConflictError):
        await svc.create_category(USER, CategoryCreate(name="AI"))
