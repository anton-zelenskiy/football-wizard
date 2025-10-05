import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.repositories.league_repository import LeagueRepository
from app.db.sqlalchemy_models import Base


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Create a database session for testing (in-memory sqlite)."""
    engine = create_async_engine('sqlite+aiosqlite:///:memory:', echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    session = session_maker()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_save_league_creates_new(db_session: AsyncSession):
    repo = LeagueRepository(db_session)
    league = await repo.save_league('Primeira Liga', 'portugal')
    assert league is not None
    assert league.id is not None
    assert league.name == 'Primeira Liga'
    assert league.country == 'Portugal'


@pytest.mark.asyncio
async def test_country_normalization(db_session: AsyncSession):
    repo = LeagueRepository(db_session)
    league1 = await repo.save_league('La Liga', 'spain')
    league2 = await repo.save_league('La Liga', 'SPAIN')
    assert league1.id == league2.id  # Same normalized country
    assert league1.country == 'Spain'


@pytest.mark.asyncio
async def test_get_by_name_and_country(db_session: AsyncSession):
    repo = LeagueRepository(db_session)
    await repo.save_league('Serie A', 'italy')

    fetched = await repo.get_by_name_and_country('Serie A', 'ITALY')
    assert fetched is not None
    assert fetched.name == 'Serie A'
    assert fetched.country == 'Italy'


@pytest.mark.asyncio
async def test_get_or_create_idempotent(db_session: AsyncSession):
    repo = LeagueRepository(db_session)
    l1 = await repo.get_or_create('Bundesliga', 'germany')
    l2 = await repo.get_or_create('Bundesliga', 'GERMANY')
    assert l1.id == l2.id
