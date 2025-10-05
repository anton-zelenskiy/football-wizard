from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.bet_rules.structures import Bet, BetType
from app.db.models import BettingOpportunity, Match
from app.db.storage import FootballDataStorage
from app.scraper.livesport_scraper import CommonMatchData


# Pytest fixtures for cleaner tests
@pytest.fixture
def storage():
    """Create FootballDataStorage instance"""
    return FootballDataStorage()


@pytest.fixture
def mock_league():
    """Create mock league"""
    league = MagicMock()
    league.id = 1
    return league


@pytest.fixture
def mock_team():
    """Create mock team"""
    team = MagicMock()
    team.id = 1
    return team


@pytest.fixture
def mock_match():
    """Create mock match"""
    match = MagicMock()
    match.id = 1
    match.status = 'scheduled'
    return match


@pytest.fixture
def sample_match_data():
    """Create sample CommonMatchData"""
    return CommonMatchData(
        home_team='Home Team',
        away_team='Away Team',
        league='Test League',
        country='Test Country',
        home_score=2,
        away_score=1,
        status='finished',
        match_date=datetime(2025, 1, 15, 15, 0),
        season=2025,
        round_number=1,
    )


def test_save_opportunity_prevents_duplicates():
    """Test that save_opportunity prevents duplicate opportunities"""
    storage = FootballDataStorage()

    # Mock the database operations
    with patch.object(storage, '_find_existing_opportunity') as mock_find:
        with patch.object(BettingOpportunity, 'save') as mock_save:
            # Test case 1: No existing opportunity (should create new)
            mock_find.return_value = None

            opportunity = Bet(
                slug='test_type',
                team_analyzed='Test Team',
                confidence=0.8,
                match_id=1,
                home_team='Home Team',
                away_team='Away Team',
                league='Test League',
                country='Test Country',
                details={},
            )

            # Mock the match lookup
            with patch.object(Match, 'get') as mock_get_match:
                mock_match = MagicMock()
                mock_match.id = 1
                mock_get_match.return_value = mock_match

                result = storage.save_opportunity(opportunity)

                # Should create new opportunity
                assert result is not None
                mock_save.assert_called_once()
                mock_find.assert_called_once_with(opportunity)


def test_save_opportunity_returns_existing_duplicate():
    """Test that save_opportunity returns existing opportunity when duplicate found"""
    storage = FootballDataStorage()

    # Mock the database operations
    with patch.object(storage, '_find_existing_opportunity') as mock_find:
        with patch.object(BettingOpportunity, 'save') as mock_save:
            # Test case 2: Existing opportunity found (should return existing)
            existing_opportunity = MagicMock()
            mock_find.return_value = existing_opportunity

            opportunity = Bet(
                slug='test_type',
                team_analyzed='Test Team',
                confidence=0.8,
                match_id=1,
                home_team='Home Team',
                away_team='Away Team',
                league='Test League',
                country='Test Country',
                details={},
            )

            # Mock the match lookup to avoid database access
            with patch.object(Match, 'get') as mock_get_match:
                mock_match = MagicMock()
                mock_match.id = 1
                mock_get_match.return_value = mock_match

                result = storage.save_opportunity(opportunity)

                # Should return existing opportunity
                assert result == existing_opportunity
                mock_save.assert_not_called()  # Should not save new one
                mock_find.assert_called_once_with(opportunity)


def test_find_existing_opportunity_with_match_id():
    """Test _find_existing_opportunity with match_id"""
    storage = FootballDataStorage()

    # Create a Bet object with match_id
    opportunity = Bet(
        rule_name='Test Rule',
        slug='test_type',
        team_analyzed='Test Team',
        confidence=0.8,
        match_id=1,
        home_team='Home Team',
        away_team='Away Team',
        league='Test League',
        country='Test Country',
        bet_type=BetType.WIN,
        details={},
    )

    # Mock database query
    with patch.object(BettingOpportunity, 'select') as mock_select:
        mock_query = MagicMock()
        mock_query.where.return_value.first.return_value = None
        mock_select.return_value = mock_query

        result = storage._find_existing_opportunity(opportunity)

        assert result is None
        mock_select.assert_called_once()


def test_find_existing_opportunity_without_match_id():
    """Test _find_existing_opportunity without match_id"""
    storage = FootballDataStorage()

    # Create a Bet object without match_id
    opportunity = Bet(
        rule_name='Test Rule',
        slug='test_type',
        team_analyzed='Test Team',
        confidence=0.8,
        match_id=None,
        home_team='Home Team',
        away_team='Away Team',
        league='Test League',
        country='Test Country',
        bet_type=BetType.WIN,
        details={},
    )

    result = storage._find_existing_opportunity(opportunity)

    assert result is None


def test_find_existing_opportunity_returns_existing():
    """Test that _find_existing_opportunity returns existing opportunity"""
    storage = FootballDataStorage()

    # Create a Bet object with match_id
    opportunity = Bet(
        rule_name='Test Rule',
        slug='test_type',
        team_analyzed='Test Team',
        confidence=0.8,
        match_id=1,
        home_team='Home Team',
        away_team='Away Team',
        league='Test League',
        country='Test Country',
        bet_type=BetType.WIN,
        details={},
    )

    # Mock database query to return an existing opportunity
    existing_opportunity = MagicMock()

    with patch.object(BettingOpportunity, 'select') as mock_select:
        mock_query = MagicMock()
        mock_query.where.return_value.first.return_value = existing_opportunity
        mock_select.return_value = mock_query

        result = storage._find_existing_opportunity(opportunity)

        # Should return the existing opportunity
        assert result == existing_opportunity
