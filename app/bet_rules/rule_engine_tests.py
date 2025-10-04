"""Tests for BettingRulesEngine with season and round-based analysis"""

from datetime import datetime
from unittest.mock import patch

import pytest

from app.bet_rules.rule_engine import BettingRulesEngine
from app.db.models import League, Match, Team, db


@pytest.fixture
def test_db():
    """Set up an in-memory test database for tests that need it"""
    # Store original database path
    original_db_path = getattr(db, 'database', None)

    try:
        # Use in-memory database (faster, no file I/O)
        db.init(':memory:')
        db.create_tables([League, Team, Match])

        # Verify we're using the test database
        assert db.database == ':memory:'

        yield

    finally:
        # Clean up
        db.close()
        # Restore original database
        if hasattr(db, 'database'):
            db.database = original_db_path


def test_rule_engine_initialization():
    """Test BettingRulesEngine initialization with custom rounds_back"""
    engine = BettingRulesEngine(rounds_back=3)
    assert engine.rounds_back == 3
    assert len(engine.rules) == 4


def test_analyze_match_with_season_round(test_db):
    """Test analyzing a match with season and round information"""
    # Use get_or_create to avoid constraint issues
    league, _ = League.get_or_create(name='Test League 1', country='Test Country 1')
    home_team, _ = Team.get_or_create(name='Home Team 1', league=league, rank=1)
    away_team, _ = Team.get_or_create(name='Away Team 1', league=league, rank=2)

    match, created = Match.get_or_create(
        league=league,
        home_team=home_team,
        away_team=away_team,
        season=2024,
        defaults={
            'match_date': datetime(2024, 3, 15, 15, 0),
            'round': 12,
            'status': 'scheduled',
        },
    )

    engine = BettingRulesEngine(rounds_back=5)

    # Mock the storage method to return empty lists (no previous matches)
    with patch.object(
        engine.storage, 'get_team_matches_by_season_and_rounds'
    ) as mock_get_matches:
        mock_get_matches.return_value = []

        opportunities = engine.analyze_match(match)

        # Should not raise errors and return empty list (no previous matches)
        assert isinstance(opportunities, list)
        assert len(opportunities) == 0

        # Verify the method was called with correct parameters
        assert mock_get_matches.call_count == 2
        mock_get_matches.assert_any_call(home_team, 2024, 12, 5)
        mock_get_matches.assert_any_call(away_team, 2024, 12, 5)


def test_analyze_match_missing_season_round():
    """Test analyzing a match without season or round information"""
    league, _ = League.get_or_create(name='Test League 2', country='Test Country 2')
    home_team, _ = Team.get_or_create(name='Home Team 2', league=league, rank=1)
    away_team, _ = Team.get_or_create(name='Away Team 2', league=league, rank=2)

    # Create a mock match object with None season/round to test the validation
    class MockMatch:
        def __init__(self):
            self.id = 999
            self.home_team = home_team
            self.away_team = away_team
            self.season = None
            self.round = None

    match = MockMatch()
    engine = BettingRulesEngine()

    opportunities = engine.analyze_match(match)

    # Should return empty list and log warning
    assert isinstance(opportunities, list)
    assert len(opportunities) == 0


def test_get_team_matches_by_season_and_rounds(test_db):
    """Test the new storage method for getting matches by season and rounds"""
    from app.db.storage import FootballDataStorage

    storage = FootballDataStorage()
    league, _ = League.get_or_create(name='Test League 5', country='Test Country 5')
    team, _ = Team.get_or_create(name='Test Team 5', league=league, rank=1)

    # Create some test matches
    opponent1, _ = Team.get_or_create(name='Opponent 1', league=league, rank=2)
    opponent2, _ = Team.get_or_create(name='Opponent 2', league=league, rank=3)

    Match.get_or_create(
        league=league,
        home_team=team,
        away_team=opponent1,
        season=2024,
        round=5,
        defaults={
            'match_date': datetime(2024, 1, 1, 15, 0),
            'status': 'finished',
            'home_score': 2,
            'away_score': 1,
        },
    )

    Match.get_or_create(
        league=league,
        home_team=opponent2,
        away_team=team,
        season=2024,
        round=6,
        defaults={
            'match_date': datetime(2024, 1, 8, 15, 0),
            'status': 'finished',
            'home_score': 1,
            'away_score': 2,
        },
    )

    # Test getting matches for round 10 (should get rounds 5-9)
    matches = storage.get_team_matches_by_season_and_rounds(team.id, 2024, 10, 5)

    # Should find the 2 matches we created (rounds 5 and 6)
    assert len(matches) == 2

    # Test getting matches for round 3 (should get rounds 1-2, but we have none)
    matches = storage.get_team_matches_by_season_and_rounds(team.id, 2024, 3, 5)
    assert len(matches) == 0


def test_get_team_matches_by_season_and_rounds_edge_cases(test_db):
    """Test edge cases for the new storage method"""
    from app.db.storage import FootballDataStorage

    storage = FootballDataStorage()
    league, _ = League.get_or_create(name='Test League 6', country='Test Country 6')
    team, _ = Team.get_or_create(name='Test Team 6', league=league, rank=1)

    # Test with round 1 (no previous rounds)
    matches = storage.get_team_matches_by_season_and_rounds(team.id, 2024, 1, 5)
    assert len(matches) == 0

    # Test with round 2 (should get round 1)
    matches = storage.get_team_matches_by_season_and_rounds(team.id, 2024, 2, 5)
    assert len(matches) == 0  # No matches in round 1
