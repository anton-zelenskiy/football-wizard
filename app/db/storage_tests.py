"""Tests for FootballDataStorage duplicate prevention functionality"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.bet_rules.models import Bet, BetType
from app.db.models import BettingOpportunity, League, Match, Team
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
    match.status = "scheduled"
    return match


@pytest.fixture
def sample_match_data():
    """Create sample CommonMatchData"""
    return CommonMatchData(
        home_team="Home Team",
        away_team="Away Team",
        league="Test League",
        country="Test Country",
        home_score=2,
        away_score=1,
        status="finished",
        match_date=datetime(2025, 1, 15, 15, 0),
        season=2025,
        round_number=1
    )


class TestDuplicatePrevention:
    """Test duplicate prevention in FootballDataStorage"""

    def test_save_opportunity_prevents_duplicates(self):
        """Test that save_opportunity prevents duplicate opportunities"""
        storage = FootballDataStorage()

        # Mock the database operations
        with patch.object(storage, '_find_existing_opportunity') as mock_find:
            with patch.object(BettingOpportunity, 'save') as mock_save:
                # Test case 1: No existing opportunity (should create new)
                mock_find.return_value = None

                opportunity = Bet(
                    rule_name='Test Rule',
                    rule_type='test_type',
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

                # Mock the match lookup
                with patch.object(storage, '_get_match_by_id') as mock_get_match:
                    mock_match = MagicMock()
                    mock_match.id = 1
                    mock_get_match.return_value = mock_match

                    result = storage.save_opportunity(opportunity)

                    # Should create new opportunity
                    assert result is not None
                    mock_save.assert_called_once()
                    mock_find.assert_called_once_with(1)  # Should check by match_id

    def test_save_opportunity_returns_existing_duplicate(self):
        """Test that save_opportunity returns existing opportunity when duplicate found"""
        storage = FootballDataStorage()

        # Mock the database operations
        with patch.object(storage, '_find_existing_opportunity') as mock_find:
            with patch.object(BettingOpportunity, 'save') as mock_save:
                # Test case 2: Existing opportunity found (should return existing)
                existing_opportunity = MagicMock()
                mock_find.return_value = existing_opportunity

                opportunity = Bet(
                    rule_name='Test Rule',
                    rule_type='test_type',
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

                # Mock the match lookup
                with patch.object(storage, '_get_match_by_id') as mock_get_match:
                    mock_match = MagicMock()
                    mock_match.id = 1
                    mock_get_match.return_value = mock_match

                    result = storage.save_opportunity(opportunity)

                    # Should return existing opportunity
                    assert result == existing_opportunity
                    mock_save.assert_not_called()  # Should not save new one
                    mock_find.assert_called_once_with(1)  # Should check by match_id

    def test_find_existing_opportunity_with_match_id(self):
        """Test _find_existing_opportunity with match_id"""
        storage = FootballDataStorage()

        # Mock database query
        with patch.object(BettingOpportunity, 'select') as mock_select:
            mock_query = MagicMock()
            mock_query.where.return_value.first.return_value = None
            mock_select.return_value = mock_query

            result = storage._find_existing_opportunity(match_id=1)

            assert result is None
            mock_select.assert_called_once()

    def test_find_existing_opportunity_without_match_id(self):
        """Test _find_existing_opportunity without match_id"""
        storage = FootballDataStorage()

        result = storage._find_existing_opportunity(match_id=None)

        assert result is None

    def test_find_existing_opportunity_returns_existing(self):
        """Test that _find_existing_opportunity returns existing opportunity"""
        storage = FootballDataStorage()

        # Mock database query to return an existing opportunity
        existing_opportunity = MagicMock()

        with patch.object(BettingOpportunity, 'select') as mock_select:
            mock_query = MagicMock()
            mock_query.where.return_value.first.return_value = existing_opportunity
            mock_select.return_value = mock_query

            result = storage._find_existing_opportunity(match_id=1)

            # Should return the existing opportunity
            assert result == existing_opportunity

    def test_get_match_by_id_success(self):
        """Test _get_match_by_id when match exists"""
        storage = FootballDataStorage()

        with patch.object(Match, 'get') as mock_get:
            mock_match = MagicMock()
            mock_get.return_value = mock_match

            result = storage._get_match_by_id(1)

            assert result == mock_match
            mock_get.assert_called_once_with(Match.id == 1)

    def test_get_match_by_id_not_found(self):
        """Test _get_match_by_id when match doesn't exist"""
        storage = FootballDataStorage()

        with patch.object(Match, 'get') as mock_get:
            mock_get.side_effect = Match.DoesNotExist()

            result = storage._get_match_by_id(1)

            assert result is None
            mock_get.assert_called_once_with(Match.id == 1)


def test_save_match_creates_new_match():
    """Test that save_match creates a new match when none exists"""
    storage = FootballDataStorage()
    
    # Create test match data
    match_data = CommonMatchData(
        home_team="Home Team",
        away_team="Away Team",
        league="Test League",
        country="Test Country",
        home_score=2,
        away_score=1,
        status="finished",
        match_date=datetime(2025, 1, 15, 15, 0),
        season=2025,
        round_number=1
    )
    
    # Mock database operations
    with patch.object(storage.db, 'atomic') as mock_atomic:
        with patch.object(League, 'get_or_create') as mock_league:
            with patch.object(Team, 'get_or_create') as mock_team:
                with patch.object(Match, 'get') as mock_get:
                    with patch.object(Match, 'create') as mock_create:
                        # Setup mocks
                        mock_league.return_value = (MagicMock(id=1), True)
                        mock_team.return_value = (MagicMock(id=1), True)
                        mock_get.side_effect = Match.DoesNotExist()
                        mock_create.return_value = MagicMock(id=1)
                        
                        # Call save_match
                        storage.save_match(match_data)
                        
                        # Verify league was created
                        mock_league.assert_called_once()
                        
                        # Verify teams were created (called twice - home and away)
                        assert mock_team.call_count == 2
                        
                        # Verify match creation was attempted
                        mock_create.assert_called_once()


def test_save_match_updates_existing_match():
    """Test that save_match updates an existing match"""
    storage = FootballDataStorage()
    
    # Create test match data
    match_data = CommonMatchData(
        home_team="Home Team",
        away_team="Away Team",
        league="Test League",
        country="Test Country",
        home_score=3,
        away_score=2,
        status="live",
        match_date=datetime.now(),
        season=2025,
        minute=45
    )
    
    # Mock existing match
    existing_match = MagicMock()
    existing_match.status = "scheduled"
    
    # Mock database operations
    with patch.object(storage.db, 'atomic') as mock_atomic:
        with patch.object(League, 'get_or_create') as mock_league:
            with patch.object(Team, 'get_or_create') as mock_team:
                with patch.object(Match, 'get') as mock_get:
                    with patch.object(storage, 'update_match_status') as mock_update:
                        # Setup mocks
                        mock_league.return_value = (MagicMock(id=1), False)
                        mock_team.return_value = (MagicMock(id=1), False)
                        mock_get.return_value = existing_match
                        
                        # Call save_match
                        storage.save_match(match_data)
                        
                        # Verify update_match_status was called
                        mock_update.assert_called_once_with(
                            existing_match,
                            "live",
                            home_score=3,
                            away_score=2,
                            minute=45,
                            red_cards_home=0,
                            red_cards_away=0
                        )


def test_save_match_normalizes_country_name():
    """Test that save_match normalizes country names"""
    storage = FootballDataStorage()
    
    # Create test match data with mixed case country
    match_data = CommonMatchData(
        home_team="Home Team",
        away_team="Away Team",
        league="Test League",
        country="test country",  # Lowercase
        season=2025
    )
    
    # Mock database operations
    with patch.object(storage.db, 'atomic') as mock_atomic:
        with patch.object(League, 'get_or_create') as mock_league:
            with patch.object(Team, 'get_or_create') as mock_team:
                with patch.object(Match, 'get') as mock_get:
                    with patch.object(Match, 'create') as mock_create:
                        # Setup mocks
                        mock_league.return_value = (MagicMock(id=1), True)
                        mock_team.return_value = (MagicMock(id=1), True)
                        mock_get.side_effect = Match.DoesNotExist()
                        mock_create.return_value = MagicMock(id=1)
                        
                        # Call save_match
                        storage.save_match(match_data)
                        
                        # Verify league was created with normalized country
                        mock_league.assert_called_once()
                        call_args = mock_league.call_args
                        assert call_args[1]['country'] == "Test Country"  # Should be title case


def test_save_match_handles_live_match_transition():
    """Test that save_match handles live match transitions correctly"""
    storage = FootballDataStorage()
    
    # Create test match data for live match
    match_data = CommonMatchData(
        home_team="Home Team",
        away_team="Away Team",
        league="Test League",
        country="Test Country",
        status="live",
        match_date=datetime.now(),
        season=2025,
        minute=30,
        red_cards_home=1,
        red_cards_away=0
    )
    
    # Mock existing scheduled match
    existing_match = MagicMock()
    existing_match.status = "scheduled"
    
    # Mock database operations
    with patch.object(storage.db, 'atomic') as mock_atomic:
        with patch.object(League, 'get_or_create') as mock_league:
            with patch.object(Team, 'get_or_create') as mock_team:
                with patch.object(Match, 'get') as mock_get:
                    with patch.object(storage, 'update_match_status') as mock_update:
                        # Setup mocks - first try to find scheduled match
                        mock_league.return_value = (MagicMock(id=1), False)
                        mock_team.return_value = (MagicMock(id=1), False)
                        mock_get.return_value = existing_match
                        
                        # Call save_match
                        storage.save_match(match_data)
                        
                        # Verify it found the scheduled match and updated it
                        mock_get.assert_called_once()
                        mock_update.assert_called_once_with(
                            existing_match,
                            "live",
                            home_score=None,
                            away_score=None,
                            minute=30,
                            red_cards_home=1,
                            red_cards_away=0
                        )


def test_save_match_creates_match_with_correct_season():
    """Test that save_match uses the correct season from match data"""
    storage = FootballDataStorage()
    
    # Create test match data with specific season
    match_data = CommonMatchData(
        home_team="Home Team",
        away_team="Away Team",
        league="Test League",
        country="Test Country",
        season=2026,  # Different season
        status="scheduled"
    )
    
    # Mock database operations
    with patch.object(storage.db, 'atomic') as mock_atomic:
        with patch.object(League, 'get_or_create') as mock_league:
            with patch.object(Team, 'get_or_create') as mock_team:
                with patch.object(Match, 'get') as mock_get:
                    with patch.object(Match, 'create') as mock_create:
                        # Setup mocks
                        mock_league.return_value = (MagicMock(id=1), True)
                        mock_team.return_value = (MagicMock(id=1), True)
                        mock_get.side_effect = Match.DoesNotExist()
                        mock_create.return_value = MagicMock(id=1)
                        
                        # Call save_match
                        storage.save_match(match_data)
                        
                        # Verify match was created with correct season
                        mock_create.assert_called_once()
                        create_call_args = mock_create.call_args[1]
                        assert create_call_args['season'] == 2026


def test_save_match_handles_finished_match():
    """Test that save_match handles finished matches correctly"""
    storage = FootballDataStorage()
    
    # Create test match data for finished match
    match_data = CommonMatchData(
        home_team="Home Team",
        away_team="Away Team",
        league="Test League",
        country="Test Country",
        home_score=2,
        away_score=1,
        status="finished",
        match_date=datetime(2025, 1, 15, 15, 0),
        season=2025,
        round_number=1
    )
    
    # Mock existing match
    existing_match = MagicMock()
    existing_match.status = "live"
    
    # Mock database operations
    with patch.object(storage.db, 'atomic') as mock_atomic:
        with patch.object(League, 'get_or_create') as mock_league:
            with patch.object(Team, 'get_or_create') as mock_team:
                with patch.object(Match, 'get') as mock_get:
                    with patch.object(storage, 'update_match_status') as mock_update:
                        # Setup mocks
                        mock_league.return_value = (MagicMock(id=1), False)
                        mock_team.return_value = (MagicMock(id=1), False)
                        mock_get.return_value = existing_match
                        
                        # Call save_match
                        storage.save_match(match_data)
                        
                        # Verify update_match_status was called with finished status
                        mock_update.assert_called_once_with(
                            existing_match,
                            "finished",
                            home_score=2,
                            away_score=1,
                            minute=None,
                            red_cards_home=0,
                            red_cards_away=0
                        )


def test_save_match_handles_scheduled_match():
    """Test that save_match handles scheduled matches correctly"""
    storage = FootballDataStorage()
    
    # Create test match data for scheduled match
    match_data = CommonMatchData(
        home_team="Home Team",
        away_team="Away Team",
        league="Test League",
        country="Test Country",
        status="scheduled",
        match_date=datetime(2025, 1, 20, 15, 0),
        season=2025,
        round_number=2
    )
    
    # Mock database operations
    with patch.object(storage.db, 'atomic') as mock_atomic:
        with patch.object(League, 'get_or_create') as mock_league:
            with patch.object(Team, 'get_or_create') as mock_team:
                with patch.object(Match, 'get') as mock_get:
                    with patch.object(Match, 'create') as mock_create:
                        # Setup mocks
                        mock_league.return_value = (MagicMock(id=1), True)
                        mock_team.return_value = (MagicMock(id=1), True)
                        mock_get.side_effect = Match.DoesNotExist()
                        mock_create.return_value = MagicMock(id=1)
                        
                        # Call save_match
                        storage.save_match(match_data)
                        
                        # Verify match was created with correct data
                        mock_create.assert_called_once()
                        create_call_args = mock_create.call_args[1]
                        assert create_call_args['status'] == "scheduled"
                        assert create_call_args['round'] == 2
                        assert create_call_args['season'] == 2025


def test_save_match_uses_core_identifying_fields():
    """Test that save_match uses core identifying fields for match lookup"""
    storage = FootballDataStorage()
    
    # Create test match data
    match_data = CommonMatchData(
        home_team="Home Team",
        away_team="Away Team",
        league="Test League",
        country="Test Country",
        season=2025
    )
    
    # Mock existing match
    existing_match = MagicMock()
    
    # Mock database operations
    with patch.object(storage.db, 'atomic') as mock_atomic:
        with patch.object(League, 'get_or_create') as mock_league:
            with patch.object(Team, 'get_or_create') as mock_team:
                with patch.object(Match, 'get') as mock_get:
                    with patch.object(storage, 'update_match_status') as mock_update:
                        # Setup mocks
                        mock_league.return_value = (MagicMock(id=1), False)
                        mock_team.return_value = (MagicMock(id=1), False)
                        mock_get.return_value = existing_match
                        
                        # Call save_match
                        storage.save_match(match_data)
                        
                        # Verify Match.get was called with core identifying fields
                        mock_get.assert_called_once()
                        call_args = mock_get.call_args[0]
                        
                        # Should be called with league, home_team, away_team, season
                        assert len(call_args) == 4  # Four conditions
