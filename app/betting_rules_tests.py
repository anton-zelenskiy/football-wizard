#!/usr/bin/env python3
"""
Unit tests for BettingRulesEngine class
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from app.betting_rules import BettingRulesEngine, BettingOpportunity
from app.db.models import League, Team, Match


@pytest.fixture
def betting_engine():
    """Create a BettingRulesEngine instance for testing"""
    return BettingRulesEngine()


@pytest.fixture
def mock_league():
    """Create a mock league for testing"""
    league = Mock(spec=League)
    league.name = 'Test League'
    league.country = 'Test Country'
    return league


@pytest.fixture
def mock_teams():
    """Create mock teams for testing"""
    home_team = Mock(spec=Team)
    home_team.name = 'Home Team'
    home_team.rank = 5
    home_team.league = Mock(spec=League)
    home_team.league.name = 'Test League'
    home_team.league.country = 'Test Country'

    away_team = Mock(spec=Team)
    away_team.name = 'Away Team'
    away_team.rank = 15
    away_team.league = Mock(spec=League)
    away_team.league.name = 'Test League'
    away_team.league.country = 'Test Country'

    return home_team, away_team


@pytest.fixture
def mock_match(mock_teams):
    """Create a mock match for testing"""
    home_team, away_team = mock_teams
    match = Mock(spec=Match)
    match.id = 1
    match.home_team = home_team
    match.away_team = away_team
    match.league = home_team.league
    match.match_date = datetime.now() + timedelta(days=1)
    match.status = 'scheduled'
    match.home_score = None
    match.away_score = None
    return match


@pytest.fixture
def mock_live_match(mock_teams):
    """Create a mock live match for testing"""
    home_team, away_team = mock_teams
    match = Mock(spec=Match)
    match.id = 2
    match.home_team = home_team
    match.away_team = away_team
    match.league = home_team.league
    match.match_date = datetime.now()
    match.status = 'live'
    match.home_score = 1
    match.away_score = 1
    match.minute = 75
    match.red_cards_home = 0
    match.red_cards_away = 1
    return match


class TestBettingRulesEngine:
    """Test cases for BettingRulesEngine class"""

    def test_init(self, betting_engine):
        """Test BettingRulesEngine initialization"""
        assert betting_engine.storage is not None
        assert betting_engine.top_teams_count > 0
        assert betting_engine.min_consecutive_losses > 0
        assert betting_engine.min_consecutive_draws > 0
        assert betting_engine.min_consecutive_losses_top5 > 0
        assert betting_engine.min_no_goals_matches > 0
        assert betting_engine.live_draw_minute_threshold > 0

    def test_calculate_team_strength_difference(self, betting_engine, mock_teams):
        """Test team strength difference calculation"""
        home_team, away_team = mock_teams

        # Test when home team is stronger (lower rank)
        strength_diff = betting_engine._calculate_team_strength_difference(home_team, away_team)
        assert strength_diff < 0  # Home team is stronger

        # Test when away team is stronger
        away_team.rank = 1
        home_team.rank = 10
        strength_diff = betting_engine._calculate_team_strength_difference(home_team, away_team)
        assert strength_diff > 0  # Away team is stronger

        # Test equal ranks
        home_team.rank = 5
        away_team.rank = 5
        strength_diff = betting_engine._calculate_team_strength_difference(home_team, away_team)
        assert strength_diff == 1  # Home advantage

    def test_analyze_team_performance(self, betting_engine, mock_teams):
        """Test team performance analysis"""
        home_team, _ = mock_teams

        with patch.object(betting_engine, '_get_recent_matches') as mock_get_matches:
            # Mock recent matches
            mock_matches = []
            for i in range(5):
                match = Mock(spec=Match)
                match.home_team = home_team
                match.away_team = Mock(spec=Team)
                match.home_score = 0
                match.away_score = 1
                mock_matches.append(match)

            mock_get_matches.return_value = mock_matches

            analysis = betting_engine._analyze_team_performance(home_team, 'home')

            assert 'consecutive_losses' in analysis
            assert 'consecutive_draws' in analysis
            assert 'consecutive_no_goals' in analysis
            assert 'is_top_team' in analysis
            assert 'is_top5_team' in analysis
            assert analysis['team'] == home_team

    def test_rule_strong_vs_weak_poor_form(self, betting_engine, mock_match):
        """Test strong vs weak poor form rule"""
        # Mock team analysis - away team is strong, home team is weak with poor form
        home_analysis = {
            'team': mock_match.home_team,
            'consecutive_losses': 3,  # Home team has poor form
            'consecutive_no_goals': 2,
            'is_top_team': False,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_losses': 0,  # Away team is strong
            'consecutive_no_goals': 0,
            'is_top_team': True,
        }

        # Mock strength difference (away team stronger) - needs to be >= 5
        with patch.object(betting_engine, '_calculate_team_strength_difference', return_value=-8):
            opportunity = betting_engine._rule_strong_vs_weak_poor_form(
                mock_match, home_analysis, away_analysis, -8
            )

            assert opportunity is not None
            assert opportunity.rule_name == 'Strong vs Weak Poor Form'
            assert opportunity.confidence > 0
            assert 'strong_team' in opportunity.details
            assert 'weak_team' in opportunity.details
            assert 'expected_outcome' in opportunity.details

    def test_rule_strong_vs_weak_poor_form_insufficient_strength_diff(
        self, betting_engine, mock_match
    ):
        """Test strong vs weak poor form rule with insufficient strength difference"""
        # Mock team analysis
        home_analysis = {
            'team': mock_match.home_team,
            'consecutive_losses': 0,
            'consecutive_no_goals': 0,
            'is_top_team': True,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_losses': 3,
            'consecutive_no_goals': 2,
            'is_top_team': False,
        }

        # Mock strength difference (less than 5) - should return None
        with patch.object(betting_engine, '_calculate_team_strength_difference', return_value=-3):
            opportunity = betting_engine._rule_strong_vs_weak_poor_form(
                mock_match, home_analysis, away_analysis, -3
            )

            assert opportunity is None

    def test_rule_both_teams_poor_form(self, betting_engine, mock_match):
        """Test both teams poor form rule"""
        # Mock team analysis with both teams having poor form
        home_analysis = {
            'team': mock_match.home_team,
            'consecutive_losses': 2,
            'consecutive_no_goals': 1,
            'is_top_team': False,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_losses': 3,
            'consecutive_no_goals': 2,
            'is_top_team': False,
        }

        opportunity = betting_engine._rule_both_teams_poor_form(
            mock_match, home_analysis, away_analysis
        )

        assert opportunity is not None
        assert opportunity.rule_name == 'Both Teams Poor Form'
        assert opportunity.confidence > 0
        assert opportunity.details['expected_outcome'] == 'draw'

    def test_rule_top_team_losing_vs_strong(self, betting_engine, mock_match):
        """Test top team losing vs strong rule"""
        # Mock team analysis
        home_analysis = {
            'team': mock_match.home_team,
            'consecutive_losses': 3,
            'consecutive_no_goals': 0,
            'is_top_team': True,
            'is_top5_team': True,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_losses': 0,
            'consecutive_no_goals': 0,
            'is_top_team': False,
            'is_top5_team': False,
        }

        # Set up opponent rank to be within 5 ranks of top team (strong opponent)
        mock_match.home_team.rank = 5
        mock_match.away_team.rank = 8  # Within 5 ranks (5 + 5 = 10, 8 <= 10)

        # Mock strength difference (away team stronger)
        with patch.object(betting_engine, '_calculate_team_strength_difference', return_value=5):
            opportunity = betting_engine._rule_top_team_losing_vs_strong(
                mock_match, home_analysis, away_analysis, 5
            )

            assert opportunity is not None
            assert opportunity.rule_name == 'Top Team Losing vs Strong'
            assert opportunity.confidence > 0
            assert 'top_team' in opportunity.details
            assert 'opponent' in opportunity.details

    def test_rule_top_team_losing_vs_weak_opponent(self, betting_engine, mock_match):
        """Test top team losing vs weak opponent (should return None)"""
        # Mock team analysis
        home_analysis = {
            'team': mock_match.home_team,
            'consecutive_losses': 3,
            'consecutive_no_goals': 0,
            'is_top_team': True,
            'is_top5_team': True,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_losses': 0,
            'consecutive_no_goals': 0,
            'is_top_team': False,
            'is_top5_team': False,
        }

        # Set up opponent rank to be more than 5 ranks away (weak opponent)
        mock_match.home_team.rank = 5
        mock_match.away_team.rank = 15  # More than 5 ranks away (5 + 5 = 10, 15 > 10)

        # Mock strength difference (away team stronger)
        with patch.object(betting_engine, '_calculate_team_strength_difference', return_value=5):
            opportunity = betting_engine._rule_top_team_losing_vs_strong(
                mock_match, home_analysis, away_analysis, 5
            )

            assert opportunity is None

    def test_rule_top_team_drawing_streak(self, betting_engine, mock_match):
        """Test top team drawing streak rule"""
        # Mock team analysis
        home_analysis = {'team': mock_match.home_team, 'consecutive_draws': 3, 'is_top_team': True}
        away_analysis = {'team': mock_match.away_team, 'consecutive_draws': 0, 'is_top_team': False}

        opportunity = betting_engine._rule_top_team_drawing_streak(
            mock_match, home_analysis, away_analysis
        )

        assert opportunity is not None
        assert opportunity.rule_name == 'Top Team Drawing Streak'
        assert opportunity.confidence > 0
        assert opportunity.details['expected_outcome'] == 'draw'

    def test_rule_top_team_no_goals_vs_strong(self, betting_engine, mock_match):
        """Test top team no goals vs strong rule"""
        # Mock team analysis
        home_analysis = {
            'team': mock_match.home_team,
            'consecutive_no_goals': 3,
            'is_top_team': True,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_no_goals': 0,
            'is_top_team': False,
        }

        # Set up opponent rank to be within 8 ranks of top team (strong opponent)
        mock_match.home_team.rank = 5
        mock_match.away_team.rank = 10  # Within 8 ranks (5 + 8 = 13, 10 <= 13)

        # Mock strength difference (away team stronger)
        with patch.object(betting_engine, '_calculate_team_strength_difference', return_value=5):
            opportunity = betting_engine._rule_top_team_no_goals_vs_strong(
                mock_match, home_analysis, away_analysis, 5
            )

            assert opportunity is not None
            assert opportunity.rule_name == 'Top Team No Goals vs Strong'
            assert opportunity.confidence > 0
            assert 'top_team' in opportunity.details
            assert 'opponent' in opportunity.details

    def test_rule_live_red_card_draw_second_half(self, betting_engine, mock_live_match):
        """Test live red card draw second half rule"""
        opportunity = betting_engine._rule_live_red_card_draw_second_half(mock_live_match)

        assert opportunity is not None
        assert opportunity.rule_name == 'Live Red Card Draw Second Half'
        assert opportunity.confidence > 0
        assert 'minute' in opportunity.details
        assert 'team_with_red' in opportunity.details
        assert 'team_against' in opportunity.details

    def test_rule_live_draw_top5_vs_below(self, betting_engine, mock_live_match):
        """Test live draw top5 vs below rule"""
        # Set up teams with appropriate ranks
        mock_live_match.home_team.rank = 3  # Top 5
        mock_live_match.away_team.rank = 12  # Below top 5

        opportunity = betting_engine._rule_live_draw_top5_vs_below(mock_live_match)

        assert opportunity is not None
        assert opportunity.rule_name == 'Live Draw Top5 vs Below'
        assert opportunity.confidence > 0
        assert 'top5_team' in opportunity.details
        assert 'other_team' in opportunity.details

    def test_analyze_scheduled_matches(self, betting_engine):
        """Test scheduled matches analysis"""
        with patch.object(betting_engine.storage, 'get_scheduled_matches') as mock_get_matches:
            # Mock scheduled matches
            mock_match = Mock(spec=Match)
            mock_match.home_team.name = 'Team A'
            mock_match.away_team.name = 'Team B'
            mock_get_matches.return_value = [mock_match]

            with patch.object(betting_engine, '_analyze_scheduled_match') as mock_analyze:
                mock_opportunity = Mock(spec=BettingOpportunity)
                mock_analyze.return_value = mock_opportunity

                opportunities = betting_engine.analyze_scheduled_matches()

                assert len(opportunities) == 1
                mock_analyze.assert_called_once_with(mock_match)

    def test_analyze_live_matches(self, betting_engine):
        """Test live matches analysis"""
        with patch.object(betting_engine.storage, 'get_recent_live_matches') as mock_get_matches:
            # Mock live matches
            mock_match = Mock(spec=Match)
            mock_get_matches.return_value = [mock_match]

            with patch.object(betting_engine, '_apply_live_rules') as mock_apply_rules:
                mock_opportunities = [Mock(spec=BettingOpportunity)]
                mock_apply_rules.return_value = mock_opportunities

                opportunities = betting_engine.analyze_live_matches()

                assert len(opportunities) == 1
                mock_apply_rules.assert_called_once_with(mock_match)

    def test_save_opportunity(self, betting_engine):
        """Test saving betting opportunity"""
        opportunity = BettingOpportunity(
            match_id=1,
            home_team='Home Team',
            away_team='Away Team',
            league='Test League',
            country='Test Country',
            rule_name='Test Rule',
            confidence=0.75,
            details={'test': 'data'},
        )

        with patch('app.betting_rules.DBBettingOpportunity') as mock_db_opportunity:
            mock_instance = Mock()
            mock_db_opportunity.return_value = mock_instance

            result = betting_engine.save_opportunity(opportunity)

            assert result == mock_instance
            mock_instance.save.assert_called_once()

    def test_team_won_lost_drew(self, betting_engine, mock_teams):
        """Test team result checking methods"""
        home_team, away_team = mock_teams

        # Test team won
        match = Mock(spec=Match)
        match.home_team = home_team
        match.away_team = away_team
        match.home_score = 2
        match.away_score = 1

        assert betting_engine._team_won(match, home_team) is True
        assert betting_engine._team_won(match, away_team) is False
        assert betting_engine._team_lost(match, home_team) is False
        assert betting_engine._team_lost(match, away_team) is True
        assert betting_engine._team_drew(match, home_team) is False

        # Test draw
        match.home_score = 1
        match.away_score = 1
        assert betting_engine._team_drew(match, home_team) is True

    def test_team_no_goals(self, betting_engine, mock_teams):
        """Test team no goals checking"""
        home_team, away_team = mock_teams

        # Test home team scored no goals
        match = Mock(spec=Match)
        match.home_team = home_team
        match.away_team = away_team
        match.home_score = 0
        match.away_score = 2

        # Ensure scores are integers, not None
        assert match.home_score is not None
        assert match.away_score is not None

        # The home team scored 0 goals, so _team_no_goals should return True
        assert betting_engine._team_no_goals(match, home_team) is True
        assert betting_engine._team_no_goals(match, away_team) is False

        # Test away team scored no goals
        match.home_score = 2
        match.away_score = 0

        assert betting_engine._team_no_goals(match, home_team) is False
        assert betting_engine._team_no_goals(match, away_team) is True

        # Test both teams scored goals
        match.home_score = 1
        match.away_score = 1

        assert betting_engine._team_no_goals(match, home_team) is False
        assert betting_engine._team_no_goals(match, away_team) is False

    def test_match_to_dict(self, betting_engine, mock_match):
        """Test match to dictionary conversion"""
        mock_match.match_date = datetime.now()
        mock_match.home_score = 2
        mock_match.away_score = 1
        mock_match.status = 'finished'

        result = betting_engine._match_to_dict(mock_match)

        assert 'date' in result
        assert 'home_team' in result
        assert 'away_team' in result
        assert 'home_score' in result
        assert 'away_score' in result
        assert 'status' in result

    def test_team_result_methods_with_none_scores(self, betting_engine, mock_teams):
        """Test team result methods with None scores"""
        home_team, away_team = mock_teams

        match = Mock(spec=Match)
        match.home_team = home_team
        match.away_team = away_team
        match.home_score = None
        match.away_score = None

        # All methods should return False when scores are None
        assert betting_engine._team_won(match, home_team) is False
        assert betting_engine._team_lost(match, home_team) is False
        assert betting_engine._team_drew(match, home_team) is False
        assert betting_engine._team_no_goals(match, home_team) is False

    def test_team_result_methods_with_partial_none_scores(self, betting_engine, mock_teams):
        """Test team result methods with partial None scores"""
        home_team, away_team = mock_teams

        match = Mock(spec=Match)
        match.home_team = home_team
        match.away_team = away_team
        match.home_score = 2
        match.away_score = None

        # All methods should return False when one score is None
        assert betting_engine._team_won(match, home_team) is False
        assert betting_engine._team_lost(match, home_team) is False
        assert betting_engine._team_drew(match, home_team) is False
        assert betting_engine._team_no_goals(match, home_team) is False

    def test_rule_edge_cases(self, betting_engine, mock_match):
        """Test edge cases for betting rules"""
        # Test with minimal strength difference
        home_analysis = {
            'team': mock_match.home_team,
            'consecutive_losses': 3,  # Home team has poor form
            'consecutive_no_goals': 2,
            'is_top_team': False,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_losses': 0,  # Away team is strong
            'consecutive_no_goals': 0,
            'is_top_team': True,
        }

        # Test with exactly 5 strength difference (boundary case)
        with patch.object(betting_engine, '_calculate_team_strength_difference', return_value=-5):
            opportunity = betting_engine._rule_strong_vs_weak_poor_form(
                mock_match, home_analysis, away_analysis, -5
            )

            assert opportunity is not None  # Should pass the >= 5 check

    def test_save_opportunity_with_none_match_id(self, betting_engine):
        """Test saving betting opportunity with None match_id"""
        opportunity = BettingOpportunity(
            match_id=None,
            home_team='Home Team',
            away_team='Away Team',
            league='Test League',
            country='Test Country',
            rule_name='Test Rule',
            confidence=0.75,
            details={'test': 'data'},
        )
        
        with patch('app.betting_rules.DBBettingOpportunity') as mock_db_opportunity:
            mock_instance = Mock()
            mock_db_opportunity.return_value = mock_instance
            
            result = betting_engine.save_opportunity(opportunity)
            
            assert result == mock_instance
            mock_instance.save.assert_called_once()

    @pytest.mark.parametrize('rank,expected_is_top', [
        (1, True),   # Rank 1 should be top team
        (3, True),   # Rank 3 (Ajax) should be top team
        (8, True),   # Rank 8 should be top team (boundary)
        (9, False),  # Rank 9 (FC Volendam) should NOT be top team
        (10, False), # Rank 10 should NOT be top team
        (15, False), # Rank 15 should NOT be top team
    ])
    def test_top_team_classification(self, betting_engine, rank, expected_is_top):
        """Test that team rank classification works correctly with top_teams_count=8"""
        is_top_team = rank <= betting_engine.top_teams_count
        assert is_top_team == expected_is_top, f"Rank {rank} should {'be' if expected_is_top else 'NOT be'} a top team"


if __name__ == '__main__':
    pytest.main([__file__])
