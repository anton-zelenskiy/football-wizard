from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.repositories.betting_opportunity_repository import (
    BettingOpportunityRepository,
)
from app.db.repositories.league_repository import LeagueRepository
from app.db.repositories.match_repository import MatchRepository
from app.db.sqlalchemy_models import Base
from app.scraper.livesport_scraper import CommonMatchData


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


async def _create_match(
    session: AsyncSession, status: str = 'scheduled', when: str = 'future'
):
    league_repo = LeagueRepository(session)
    match_repo = MatchRepository(session)
    await league_repo.save_league('Test League', 'Country')
    match_date = datetime.now() + (
        timedelta(days=1) if when == 'future' else timedelta(days=-1)
    )
    data = CommonMatchData(
        home_team='Home',
        away_team='Away',
        league='Test League',
        country='Country',
        status=status,
        season=2024,
        match_date=match_date,
        home_score=1 if status == 'finished' else None,
        away_score=0 if status == 'finished' else None,
    )
    return await match_repo.save_match(data)


@pytest.mark.asyncio
async def test_save_opportunity_and_prevent_duplicates(db_session: AsyncSession):
    opp_repo = BettingOpportunityRepository(db_session)
    match = await _create_match(db_session, status='scheduled', when='future')

    o1 = await opp_repo.save_opportunity(
        match_id=match.id,
        rule_slug='consecutive_losses',
        confidence_score=0.7,
        details={'k': 'v'},
        team_analyzed='Home',
    )
    o2 = await opp_repo.save_opportunity(
        match_id=match.id,
        rule_slug='consecutive_losses',
        confidence_score=0.9,
        details={'k': 'v2'},
        team_analyzed='Home',
    )
    assert o1.id == o2.id  # duplicate prevented while pending


@pytest.mark.asyncio
async def test_get_active_betting_opportunities(db_session: AsyncSession):
    opp_repo = BettingOpportunityRepository(db_session)
    match = await _create_match(db_session, status='scheduled', when='future')
    await opp_repo.save_opportunity(
        match_id=match.id,
        rule_slug='consecutive_losses',
        confidence_score=0.6,
        details={},
    )

    items = await opp_repo.get_active_betting_opportunities()
    assert len(items) == 1
    assert items[0].match_id == match.id


@pytest.mark.asyncio
async def test_get_completed_betting_opportunities(db_session: AsyncSession):
    opp_repo = BettingOpportunityRepository(db_session)
    match = await _create_match(db_session, status='finished', when='past')
    await opp_repo.save_opportunity(
        match_id=match.id,
        rule_slug='consecutive_losses',
        confidence_score=0.6,
        details={'team_analyzed': 'Home'},
    )

    # Update outcomes first to ensure it's completed
    await opp_repo.update_betting_outcomes()
    items = await opp_repo.get_completed_betting_opportunities()
    assert len(items) == 1
    assert items[0].match_id == match.id


@pytest.mark.asyncio
async def test_get_betting_statistics(db_session: AsyncSession):
    opp_repo = BettingOpportunityRepository(db_session)
    match = await _create_match(db_session, status='finished', when='past')
    await opp_repo.save_opportunity(
        match_id=match.id,
        rule_slug='consecutive_losses',
        confidence_score=0.6,
        details={'team_analyzed': 'Home'},
    )

    # Determine outcomes first, then stats should reflect at least one completed
    await opp_repo.update_betting_outcomes()
    stats = await opp_repo.get_betting_statistics()
    assert stats['total'] >= 1
    assert 'win_rate' in stats


@pytest.mark.asyncio
async def test_update_betting_outcomes(db_session: AsyncSession):
    opp_repo = BettingOpportunityRepository(db_session)
    match = await _create_match(db_session, status='finished', when='past')
    await opp_repo.save_opportunity(
        match_id=match.id,
        rule_slug='consecutive_losses',
        confidence_score=0.6,
        details={'team_analyzed': 'Home'},
    )

    updated = await opp_repo.update_betting_outcomes()
    assert isinstance(updated, int)
