from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.repositories.match_repository import MatchRepository
from app.db.sqlalchemy_models import Base
from app.scraper.livesport_scraper import CommonMatchData


@pytest_asyncio.fixture
async def db_session():
    """Create a database session for testing."""
    # Create in-memory SQLite database for testing
    engine = create_async_engine('sqlite+aiosqlite:///:memory:', echo=False)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    session_local = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    session = session_local()

    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_save_new_match(db_session):
    """Test saving a new match"""
    repo = MatchRepository(db_session)

    # Create test match data
    match_data = CommonMatchData(
        home_team='Home Team',
        away_team='Away Team',
        league='Test League',
        country='Test Country',
        home_score=2,
        away_score=1,
        status='finished',
        match_date=datetime.now(),
        season=2024,
        round_number=1,
    )

    # Save match
    match = await repo.save_match(match_data)

    assert match is not None
    assert match.home_score == 2
    assert match.away_score == 1
    assert match.status == 'finished'
    assert match.season == 2024
    assert match.round == 1


@pytest.mark.asyncio
async def test_save_existing_match_update(db_session):
    """Test updating an existing match"""
    repo = MatchRepository(db_session)

    # Create initial match data
    match_data = CommonMatchData(
        home_team='Home Team',
        away_team='Away Team',
        league='Test League',
        country='Test Country',
        status='scheduled',
        season=2024,
    )

    # Save initial match
    match1 = await repo.save_match(match_data)
    assert match1.status == 'scheduled'

    # Update match data
    match_data.status = 'live'
    match_data.minute = 30
    match_data.home_score = 1
    match_data.away_score = 0

    # Save updated match
    match2 = await repo.save_match(match_data)

    assert match2.id == match1.id  # Same match
    assert match2.status == 'live'
    assert match2.minute == 30
    assert match2.home_score == 1
    assert match2.away_score == 0


@pytest.mark.asyncio
async def test_save_match_creates_league_and_teams(db_session):
    """Test that save_match creates league and teams if they don't exist"""
    repo = MatchRepository(db_session)

    # Create test match data
    match_data = CommonMatchData(
        home_team='New Home Team',
        away_team='New Away Team',
        league='New League',
        country='New Country',
        status='scheduled',
        season=2024,
    )

    # Save match
    match = await repo.save_match(match_data)

    assert match is not None
    assert match.league_id is not None
    assert match.home_team_id is not None
    assert match.away_team_id is not None

    # Verify league was created
    from app.db.sqlalchemy_models import League

    league_result = await db_session.execute(
        select(League).where(League.id == match.league_id)
    )
    league = league_result.scalar_one_or_none()
    assert league is not None
    assert league.name == 'New League'
    assert league.country == 'New Country'

    # Verify teams were created
    from app.db.sqlalchemy_models import Team

    home_team_result = await db_session.execute(
        select(Team).where(Team.id == match.home_team_id)
    )
    home_team = home_team_result.scalar_one_or_none()
    assert home_team is not None
    assert home_team.name == 'New Home Team'

    away_team_result = await db_session.execute(
        select(Team).where(Team.id == match.away_team_id)
    )
    away_team = away_team_result.scalar_one_or_none()
    assert away_team is not None
    assert away_team.name == 'New Away Team'


@pytest.mark.asyncio
async def test_update_match_status(db_session):
    """Test updating match status"""
    repo = MatchRepository(db_session)

    # Create match
    match_data = CommonMatchData(
        home_team='Home Team',
        away_team='Away Team',
        league='Test League',
        country='Test Country',
        status='scheduled',
        season=2024,
    )

    match = await repo.save_match(match_data)

    # Update status to live
    updated_match = await repo.update_match_status(
        match.id, 'live', minute=45, home_score=1, away_score=0
    )

    assert updated_match is not None
    assert updated_match.status == 'live'
    assert updated_match.minute == 45
    assert updated_match.home_score == 1
    assert updated_match.away_score == 0


@pytest.mark.asyncio
async def test_update_match_status_finished(db_session):
    """Test updating match status to finished"""
    repo = MatchRepository(db_session)

    # Create live match
    match_data = CommonMatchData(
        home_team='Home Team',
        away_team='Away Team',
        league='Test League',
        country='Test Country',
        status='live',
        minute=90,
        home_score=1,
        away_score=0,
        season=2024,
    )

    match = await repo.save_match(match_data)

    # Update status to finished
    updated_match = await repo.update_match_status(
        match.id, 'finished', home_score=2, away_score=1
    )

    assert updated_match is not None
    assert updated_match.status == 'finished'
    assert updated_match.minute is None  # Cleared for finished matches
    assert updated_match.red_cards_home == 0  # Reset to default
    assert updated_match.red_cards_away == 0  # Reset to default
    assert updated_match.home_score == 2
    assert updated_match.away_score == 1
