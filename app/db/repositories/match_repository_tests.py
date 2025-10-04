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


@pytest.mark.asyncio
async def test_get_matches_by_status_scheduled(db_session):
    """Test getting scheduled matches"""
    repo = MatchRepository(db_session)

    # Create multiple matches with different statuses
    scheduled_data = CommonMatchData(
        home_team='Scheduled Home',
        away_team='Scheduled Away',
        league='Test League',
        country='Test Country',
        status='scheduled',
        season=2024,
        match_date=datetime(2024, 1, 15, 15, 0),
    )

    live_data = CommonMatchData(
        home_team='Live Home',
        away_team='Live Away',
        league='Test League',
        country='Test Country',
        status='live',
        season=2024,
        match_date=datetime(2024, 1, 15, 16, 0),
    )

    finished_data = CommonMatchData(
        home_team='Finished Home',
        away_team='Finished Away',
        league='Test League',
        country='Test Country',
        status='finished',
        season=2024,
        match_date=datetime(2024, 1, 15, 14, 0),
    )

    # Save all matches
    await repo.save_match(scheduled_data)
    await repo.save_match(live_data)
    await repo.save_match(finished_data)

    # Get scheduled matches
    scheduled_matches = await repo.get_matches_by_status('scheduled')

    assert len(scheduled_matches) == 1
    assert scheduled_matches[0].status == 'scheduled'
    assert scheduled_matches[0].home_team.name == 'Scheduled Home'
    assert scheduled_matches[0].away_team.name == 'Scheduled Away'


@pytest.mark.asyncio
async def test_get_matches_by_status_live(db_session):
    """Test getting live matches"""
    repo = MatchRepository(db_session)

    # Create live matches
    live_data1 = CommonMatchData(
        home_team='Live Home 1',
        away_team='Live Away 1',
        league='Test League',
        country='Test Country',
        status='live',
        season=2024,
        minute=30,
    )

    live_data2 = CommonMatchData(
        home_team='Live Home 2',
        away_team='Live Away 2',
        league='Test League',
        country='Test Country',
        status='live',
        season=2024,
        minute=60,
    )

    # Save matches
    await repo.save_match(live_data1)
    await repo.save_match(live_data2)

    # Get live matches
    live_matches = await repo.get_matches_by_status('live')

    assert len(live_matches) == 2
    for match in live_matches:
        assert match.status == 'live'
        assert match.minute is not None


@pytest.mark.asyncio
async def test_get_matches_by_status_finished(db_session):
    """Test getting finished matches"""
    repo = MatchRepository(db_session)

    # Create finished matches
    finished_data1 = CommonMatchData(
        home_team='Finished Home 1',
        away_team='Finished Away 1',
        league='Test League',
        country='Test Country',
        status='finished',
        season=2024,
        home_score=2,
        away_score=1,
    )

    finished_data2 = CommonMatchData(
        home_team='Finished Home 2',
        away_team='Finished Away 2',
        league='Test League',
        country='Test Country',
        status='finished',
        season=2024,
        home_score=0,
        away_score=3,
    )

    # Save matches
    await repo.save_match(finished_data1)
    await repo.save_match(finished_data2)

    # Get finished matches
    finished_matches = await repo.get_matches_by_status('finished')

    assert len(finished_matches) == 2
    for match in finished_matches:
        assert match.status == 'finished'
        assert match.home_score is not None
        assert match.away_score is not None


@pytest.mark.asyncio
async def test_get_matches_by_status_empty_result(db_session):
    """Test getting matches by status when no matches exist"""
    repo = MatchRepository(db_session)

    # Try to get matches for a status that doesn't exist
    matches = await repo.get_matches_by_status('nonexistent')

    assert len(matches) == 0


@pytest.mark.asyncio
async def test_get_team_matches_by_season_and_rounds(db_session):
    """Test getting team matches by season and rounds"""
    repo = MatchRepository(db_session)

    # Create a team and league first
    from app.db.sqlalchemy_models import League, Team

    league = League(name='Test League', country='Test Country')
    db_session.add(league)
    await db_session.commit()
    await db_session.refresh(league)

    team = Team(name='Test Team', league_id=league.id)
    db_session.add(team)
    await db_session.commit()
    await db_session.refresh(team)

    # Create matches for the team in different rounds
    for round_num in range(1, 6):  # Rounds 1-5
        match_data = CommonMatchData(
            home_team='Test Team' if round_num % 2 == 1 else f'Other Team {round_num}',
            away_team=f'Other Team {round_num}' if round_num % 2 == 1 else 'Test Team',
            league='Test League',
            country='Test Country',
            status='finished',
            season=2024,
            round_number=round_num,
            home_score=1,
            away_score=0,
            match_date=datetime(2024, 1, 10 + round_num),
        )
        await repo.save_match(match_data)

    # Get matches for rounds 2-4 (current round 5, looking back 3 rounds)
    matches = await repo.get_team_matches_by_season_and_rounds(
        team.id, 2024, 5, rounds_back=3
    )

    assert len(matches) == 3  # Rounds 2, 3, 4
    # Should be ordered by round desc, then match_date desc
    assert matches[0].round == 4
    assert matches[1].round == 3
    assert matches[2].round == 2


@pytest.mark.asyncio
async def test_get_team_matches_by_season_and_rounds_insufficient_rounds(db_session):
    """Test getting team matches when there are insufficient previous rounds"""
    repo = MatchRepository(db_session)

    # Create a team and league first
    from app.db.sqlalchemy_models import League, Team

    league = League(name='Test League', country='Test Country')
    db_session.add(league)
    await db_session.commit()
    await db_session.refresh(league)

    team = Team(name='Test Team', league_id=league.id)
    db_session.add(team)
    await db_session.commit()
    await db_session.refresh(team)

    # Create only round 1 match
    match_data = CommonMatchData(
        home_team='Test Team',
        away_team='Other Team 1',
        league='Test League',
        country='Test Country',
        status='finished',
        season=2024,
        round_number=1,
        home_score=1,
        away_score=0,
    )
    await repo.save_match(match_data)

    # Try to get matches for round 1 looking back 3 rounds (would need rounds -2, -1, 0)
    matches = await repo.get_team_matches_by_season_and_rounds(
        team.id, 2024, 1, rounds_back=3
    )

    assert len(matches) == 0  # No previous rounds available


@pytest.mark.asyncio
async def test_get_team_matches_by_season_and_rounds_different_seasons(db_session):
    """Test that matches from different seasons are not included"""
    repo = MatchRepository(db_session)

    # Create a team and league first
    from app.db.sqlalchemy_models import League, Team

    league = League(name='Test League', country='Test Country')
    db_session.add(league)
    await db_session.commit()
    await db_session.refresh(league)

    team = Team(name='Test Team', league_id=league.id)
    db_session.add(team)
    await db_session.commit()
    await db_session.refresh(team)

    # Create matches in different seasons
    for season in [2023, 2024]:
        for round_num in range(1, 4):
            match_data = CommonMatchData(
                home_team='Test Team',
                away_team=f'Other Team {season}_{round_num}',
                league='Test League',
                country='Test Country',
                status='finished',
                season=season,
                round_number=round_num,
                home_score=1,
                away_score=0,
            )
            await repo.save_match(match_data)

    # Get matches for 2024 season only
    matches = await repo.get_team_matches_by_season_and_rounds(
        team.id, 2024, 4, rounds_back=2
    )

    assert len(matches) == 2  # Only 2024 matches (rounds 2, 3)
    for match in matches:
        assert match.season == 2024


@pytest.mark.asyncio
async def test_get_team_matches_by_season_and_rounds_only_finished_matches(db_session):
    """Test that only finished matches are returned"""
    repo = MatchRepository(db_session)

    # Create a team and league first
    from app.db.sqlalchemy_models import League, Team

    league = League(name='Test League', country='Test Country')
    db_session.add(league)
    await db_session.commit()
    await db_session.refresh(league)

    team = Team(name='Test Team', league_id=league.id)
    db_session.add(team)
    await db_session.commit()
    await db_session.refresh(team)

    # Create matches with different statuses
    for status in ['scheduled', 'live', 'finished']:
        match_data = CommonMatchData(
            home_team='Test Team',
            away_team=f'Other Team {status}',
            league='Test League',
            country='Test Country',
            status=status,
            season=2024,
            round_number=1,
            home_score=1 if status == 'finished' else None,
            away_score=0 if status == 'finished' else None,
        )
        await repo.save_match(match_data)

    # Get matches - should only return finished ones
    matches = await repo.get_team_matches_by_season_and_rounds(
        team.id, 2024, 2, rounds_back=1
    )

    assert len(matches) == 1  # Only the finished match
    assert matches[0].status == 'finished'


@pytest.mark.asyncio
async def test_get_team_matches_by_season_and_rounds_ordering(db_session):
    """Test that matches are ordered correctly (round desc, match_date desc)"""
    repo = MatchRepository(db_session)

    # Create a team and league first
    from app.db.sqlalchemy_models import League, Team

    league = League(name='Test League', country='Test Country')
    db_session.add(league)
    await db_session.commit()
    await db_session.refresh(league)

    team = Team(name='Test Team', league_id=league.id)
    db_session.add(team)
    await db_session.commit()
    await db_session.refresh(team)

    # Create matches with specific dates to test ordering
    match_data1 = CommonMatchData(
        home_team='Test Team',
        away_team='Other Team 1',
        league='Test League',
        country='Test Country',
        status='finished',
        season=2024,
        round_number=3,
        home_score=1,
        away_score=0,
        match_date=datetime(2024, 1, 15),  # Later date
    )
    await repo.save_match(match_data1)

    match_data2 = CommonMatchData(
        home_team='Test Team',
        away_team='Other Team 2',
        league='Test League',
        country='Test Country',
        status='finished',
        season=2024,
        round_number=3,
        home_score=1,
        away_score=0,
        match_date=datetime(2024, 1, 10),  # Earlier date
    )
    await repo.save_match(match_data2)

    match_data3 = CommonMatchData(
        home_team='Test Team',
        away_team='Other Team 3',
        league='Test League',
        country='Test Country',
        status='finished',
        season=2024,
        round_number=2,
        home_score=1,
        away_score=0,
        match_date=datetime(2024, 1, 20),  # Latest date but lower round
    )
    await repo.save_match(match_data3)

    # Get matches
    matches = await repo.get_team_matches_by_season_and_rounds(
        team.id, 2024, 4, rounds_back=2
    )

    assert len(matches) == 3
    # Should be ordered by round desc (3, 3, 2), then by match_date desc within same round
    assert matches[0].round == 3
    assert matches[0].match_date == datetime(2024, 1, 15)  # Later date first
    assert matches[1].round == 3
    assert matches[1].match_date == datetime(2024, 1, 10)  # Earlier date second
    assert matches[2].round == 2
    assert matches[2].match_date == datetime(2024, 1, 20)  # Lower round last
