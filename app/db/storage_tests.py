"""Tests for FootballDataStorage duplicate prevention functionality"""

from unittest.mock import MagicMock, patch

import pytest

from app.bet_rules.models import Bet, BetType
from app.db.models import BettingOpportunity, League, Match, Team
from app.db.storage import FootballDataStorage


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
