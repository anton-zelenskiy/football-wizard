import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.repositories.league_repository import LeagueRepository
from app.db.repositories.team_repository import TeamRepository
from app.db.repositories.team_standing_repository import TeamStandingRepository
from app.db.sqlalchemy_models import Base
from app.scraper.constants import DEFAULT_SEASON


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
    standing_repo = TeamStandingRepository(db_session)

    # Ensure league exists
    league = await league_repo.save_league('Test League', 'spain')

    # Create team standings
    data = make_standings('Valencia', rank=5)
    team, _ = await team_repo.save_team_standings(data, 'Test League', 'SPAIN')
    assert team is not None
    assert team.name == 'Valencia'

    # Check TeamStanding instead of Team
    standing = await standing_repo.get_by_team_league_season(
        team.id, league.id, DEFAULT_SEASON
    )
    assert standing is not None
    assert standing.rank == 5
    assert standing.points == 20

    # Update standings
    updated = make_standings('Valencia', rank=3, points=24)
    team2, _ = await team_repo.save_team_standings(updated, 'Test League', 'Spain')
    assert team2.id == team.id

    # Check updated TeamStanding
    standing2 = await standing_repo.get_by_team_league_season(
        team2.id, league.id, DEFAULT_SEASON
    )
    assert standing2 is not None
    assert standing2.rank == 3
    assert standing2.points == 24


@pytest.mark.asyncio
async def test_save_team_standings_league_not_found(db_session: AsyncSession):
    team_repo = TeamRepository(db_session)
    data = make_standings('Unknown FC')
    result = await team_repo.save_team_standings(data, 'Missing League', 'Italy')
    assert result[0] is None
