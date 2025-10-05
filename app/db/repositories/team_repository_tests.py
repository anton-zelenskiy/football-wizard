import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.repositories.league_repository import LeagueRepository
from app.db.repositories.team_repository import TeamRepository
from app.db.sqlalchemy_models import Base


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    engine = create_async_engine('sqlite+aiosqlite:///:memory:', echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_local = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    session = session_local()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


def make_standings(
    team_name: str,
    rank: int = 1,
    played: int = 10,
    win: int = 6,
    draw: int = 2,
    lose: int = 2,
    points: int = 20,
):
    return {
        'team': {'name': team_name},
        'rank': rank,
        'all': {
            'played': played,
            'win': win,
            'draw': draw,
            'lose': lose,
            'goals': {'for': 18, 'against': 9},
        },
        'points': points,
    }


@pytest.mark.asyncio
async def test_save_team_standings_creates_and_updates(db_session: AsyncSession):
    league_repo = LeagueRepository(db_session)
    team_repo = TeamRepository(db_session)

    # Ensure league exists
    await league_repo.save_league('Test League', 'spain')

    # Create team standings
    data = make_standings('Valencia', rank=5)
    team = await team_repo.save_team_standings(data, 'Test League', 'SPAIN')
    assert team is not None
    assert team.name == 'Valencia'
    assert team.rank == 5
    assert team.points == 20

    # Update standings
    updated = make_standings('Valencia', rank=3, points=24)
    team2 = await team_repo.save_team_standings(updated, 'Test League', 'Spain')
    assert team2.id == team.id
    assert team2.rank == 3
    assert team2.points == 24


@pytest.mark.asyncio
async def test_save_team_standings_league_not_found(db_session: AsyncSession):
    team_repo = TeamRepository(db_session)
    data = make_standings('Unknown FC')
    result = await team_repo.save_team_standings(data, 'Missing League', 'Italy')
    assert result is None
