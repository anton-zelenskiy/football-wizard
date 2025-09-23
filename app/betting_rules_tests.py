#!/usr/bin/env python3
"""
Unit tests for BettingRulesEngine class
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.betting_rules import BettingOpportunity, BettingRulesEngine
from app.db.models import League, Match, Team


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
            # Mock recent matches with varied outcomes
            mock_matches = []
            for i in range(10):
                match = Mock(spec=Match)
                match.home_team = home_team
                match.away_team = Mock(spec=Team)

                # Create a pattern: first 3 wins, then 2 losses, then 2 draws, then 3 wins
                if i < 3:
                    match.home_score = 2
                    match.away_score = 0
                elif i < 5:
                    match.home_score = 0
                    match.away_score = 1
                elif i < 7:
                    match.home_score = 1
                    match.away_score = 1
                else:
                    match.home_score = 2
                    match.away_score = 1

                mock_matches.append(match)

            mock_get_matches.return_value = mock_matches

            analysis = betting_engine._analyze_team_performance(home_team, 'home')

            # Test basic fields
            assert 'consecutive_wins' in analysis
            assert 'consecutive_losses' in analysis
            assert 'consecutive_draws' in analysis
            assert 'consecutive_no_goals' in analysis
            assert 'consecutive_goals' in analysis
            assert 'is_top_team' in analysis
            assert 'is_top5_team' in analysis
            assert 'total_matches' in analysis
            assert 'wins' in analysis
            assert 'draws' in analysis
            assert 'losses' in analysis
            assert 'win_rate' in analysis
            assert 'draw_rate' in analysis
            assert 'loss_rate' in analysis
            assert analysis['team'] == home_team

            # Test calculated values
            assert analysis['total_matches'] == 10
            assert analysis['wins'] == 6  # 3 + 3
            assert analysis['draws'] == 2
            assert analysis['losses'] == 2
            assert analysis['win_rate'] == 0.6
            assert analysis['draw_rate'] == 0.2
            assert analysis['loss_rate'] == 0.2

    def test_calculate_consecutive_streak(self, betting_engine, mock_teams):
        """Test consecutive streak calculation"""
        home_team, _ = mock_teams

        # Test 1: Simple consecutive wins pattern
        # Most recent first: [win, win, win, loss, loss]
        win_pattern = [
            (2, 0),
            (3, 1),
            (1, 0),  # 3 wins (most recent first)
            (0, 1),
            (0, 2),  # 2 losses
        ]

        win_matches = []
        for home_score, away_score in win_pattern:
            match = Mock(spec=Match)
            match.home_team = home_team
            match.away_team = Mock(spec=Team)
            match.home_score = home_score
            match.away_score = away_score
            win_matches.append(match)

        # Consecutive wins should be 3 from the beginning (most recent)
        consecutive_wins = betting_engine._calculate_consecutive_streak(
            win_matches, home_team, 'win'
        )
        assert consecutive_wins == 3

        # Test 2: Consecutive no-goals pattern
        # Most recent first: [no-goals, no-goals, goals, goals]
        no_goals_pattern = [
            (0, 1),
            (0, 2),  # 2 no-goals (most recent first)
            (1, 0),
            (2, 1),  # 2 with goals
        ]

        no_goals_matches = []
        for home_score, away_score in no_goals_pattern:
            match = Mock(spec=Match)
            match.home_team = home_team
            match.away_team = Mock(spec=Team)
            match.home_score = home_score
            match.away_score = away_score
            no_goals_matches.append(match)

        # Consecutive no-goals should be 2 from the beginning (most recent)
        consecutive_no_goals = betting_engine._calculate_consecutive_streak(
            no_goals_matches, home_team, 'no_goals'
        )
        assert consecutive_no_goals == 2

        # Test 3: Mixed pattern
        # Most recent first: [no-goals, no-goals, goals, win, loss]
        mixed_pattern = [
            (0, 1),
            (0, 2),  # 2 no-goals (most recent first)
            (1, 0),  # 1 with goals
            (2, 0),
            (0, 1),  # 1 win, 1 loss
        ]

        mixed_matches = []
        for home_score, away_score in mixed_pattern:
            match = Mock(spec=Match)
            match.home_team = home_team
            match.away_team = Mock(spec=Team)
            match.home_score = home_score
            match.away_score = away_score
            mixed_matches.append(match)

        # Consecutive draws should be 0 since most recent match is not a draw
        consecutive_draws = betting_engine._calculate_consecutive_streak(
            mixed_matches, home_team, 'draw'
        )
        assert consecutive_draws == 0

        # Consecutive no-goals should be 2 from the beginning (most recent)
        # Pattern: [no-goals(0,1), no-goals(0,2), goals(1,0), win(2,0), loss(0,1)]
        # So from the beginning: no-goals, no-goals = 2 no-goals
        consecutive_no_goals = betting_engine._calculate_consecutive_streak(
            mixed_matches, home_team, 'no_goals'
        )
        assert consecutive_no_goals == 2

        # Consecutive wins should be 0 since most recent match is not a win
        consecutive_wins = betting_engine._calculate_consecutive_streak(
            mixed_matches, home_team, 'win'
        )
        assert consecutive_wins == 0

        # Consecutive losses should be 2 since most recent matches are losses
        consecutive_losses = betting_engine._calculate_consecutive_streak(
            mixed_matches, home_team, 'loss'
        )
        assert consecutive_losses == 2

    def test_rule_winning_streak_vs_losing_streak(self, betting_engine, mock_match):
        """Test winning streak vs losing streak rule"""
        # Mock team analysis - home team on winning streak, away team on losing streak
        home_analysis = {
            'team': mock_match.home_team,
            'consecutive_wins': 4,  # Home team on winning streak
            'consecutive_losses': 0,
            'consecutive_draws': 0,
            'consecutive_no_goals': 0,
            'consecutive_goals': 4,
            'is_top_team': False,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_wins': 0,
            'consecutive_losses': 3,  # Away team on losing streak
            'consecutive_draws': 0,
            'consecutive_no_goals': 2,
            'consecutive_goals': 0,
            'is_top_team': False,
        }

        opportunity = betting_engine._rule_winning_streak_vs_losing_streak(
            mock_match, home_analysis, away_analysis
        )

        assert opportunity is not None
        assert opportunity.rule_name == 'Winning Streak vs Losing Streak'
        assert opportunity.confidence > 0.65
        assert opportunity.details['winning_team'] == mock_match.home_team.name
        assert opportunity.details['losing_team'] == mock_match.away_team.name
        assert opportunity.details['winning_streak'] == 4
        assert opportunity.details['losing_streak'] == 3
        assert opportunity.details['expected_outcome'] == f'{mock_match.home_team.name} to win'

    def test_rule_winning_streak_vs_losing_streak_away_team(self, betting_engine, mock_match):
        """Test winning streak vs losing streak rule with away team winning"""
        # Mock team analysis - away team on winning streak, home team on losing streak
        home_analysis = {
            'team': mock_match.home_team,
            'consecutive_wins': 0,
            'consecutive_losses': 3,  # Home team on losing streak
            'consecutive_draws': 0,
            'consecutive_no_goals': 2,
            'consecutive_goals': 0,
            'is_top_team': False,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_wins': 5,  # Away team on winning streak
            'consecutive_losses': 0,
            'consecutive_draws': 0,
            'consecutive_no_goals': 0,
            'consecutive_goals': 5,
            'is_top_team': False,
        }

        opportunity = betting_engine._rule_winning_streak_vs_losing_streak(
            mock_match, home_analysis, away_analysis
        )

        assert opportunity is not None
        assert opportunity.rule_name == 'Winning Streak vs Losing Streak'
        assert opportunity.confidence > 0.65
        assert opportunity.details['winning_team'] == mock_match.away_team.name
        assert opportunity.details['losing_team'] == mock_match.home_team.name
        assert opportunity.details['winning_streak'] == 5
        assert opportunity.details['losing_streak'] == 3
        assert opportunity.details['expected_outcome'] == f'{mock_match.away_team.name} to win'

    def test_rule_winning_streak_vs_losing_streak_insufficient_streaks(
        self, betting_engine, mock_match
    ):
        """Test winning streak vs losing streak rule with insufficient streaks"""
        # Mock team analysis - insufficient streaks
        home_analysis = {
            'team': mock_match.home_team,
            'consecutive_wins': 2,  # Only 2 wins (need 3+)
            'consecutive_losses': 0,
            'consecutive_draws': 0,
            'consecutive_no_goals': 0,
            'consecutive_goals': 2,
            'is_top_team': False,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_wins': 0,
            'consecutive_losses': 1,  # Only 1 loss (need 2+)
            'consecutive_draws': 0,
            'consecutive_no_goals': 1,
            'consecutive_goals': 0,
            'is_top_team': False,
        }

        opportunity = betting_engine._rule_winning_streak_vs_losing_streak(
            mock_match, home_analysis, away_analysis
        )

        assert opportunity is None

    def test_rule_high_scoring_vs_low_scoring(self, betting_engine, mock_match):
        """Test high scoring vs low scoring rule"""
        # Mock team analysis - home team scoring consistently, away team not scoring
        home_analysis = {
            'team': mock_match.home_team,
            'consecutive_wins': 2,
            'consecutive_losses': 0,
            'consecutive_draws': 0,
            'consecutive_no_goals': 0,
            'consecutive_goals': 4,  # Home team scoring consistently
            'is_top_team': False,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_wins': 0,
            'consecutive_losses': 2,
            'consecutive_draws': 0,
            'consecutive_no_goals': 3,  # Away team not scoring
            'consecutive_goals': 0,
            'is_top_team': False,
        }

        opportunity = betting_engine._rule_high_scoring_vs_low_scoring(
            mock_match, home_analysis, away_analysis
        )

        assert opportunity is not None
        assert opportunity.rule_name == 'High Scoring vs Low Scoring'
        assert opportunity.confidence == 0.75
        assert opportunity.details['high_scoring_team'] == mock_match.home_team.name
        assert opportunity.details['low_scoring_team'] == mock_match.away_team.name
        assert opportunity.details['home_goals_streak'] == 4
        assert opportunity.details['away_no_goals_streak'] == 3
        assert (
            opportunity.details['expected_outcome']
            == f'{mock_match.home_team.name} to win with goals'
        )

    def test_rule_both_teams_good_form(self, betting_engine, mock_match):
        """Test both teams good form rule"""
        # Mock team analysis - both teams in good form and scoring
        home_analysis = {
            'team': mock_match.home_team,
            'consecutive_wins': 3,  # Good form
            'consecutive_losses': 0,
            'consecutive_draws': 0,
            'consecutive_no_goals': 0,
            'consecutive_goals': 4,  # Scoring consistently
            'win_rate': 0.7,  # Good win rate
            'is_top_team': False,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_wins': 2,  # Good form
            'consecutive_losses': 0,
            'consecutive_draws': 0,
            'consecutive_no_goals': 0,
            'consecutive_goals': 3,  # Scoring consistently
            'win_rate': 0.65,  # Good win rate
            'is_top_team': False,
        }

        opportunity = betting_engine._rule_both_teams_good_form(
            mock_match, home_analysis, away_analysis
        )

        assert opportunity is not None
        assert opportunity.rule_name == 'Both Teams Good Form'
        assert opportunity.confidence == 0.70
        assert opportunity.details['home_team'] == mock_match.home_team.name
        assert opportunity.details['away_team'] == mock_match.away_team.name
        assert opportunity.details['home_win_rate'] == 0.7
        assert opportunity.details['away_win_rate'] == 0.65
        assert opportunity.details['home_goals_streak'] == 4
        assert opportunity.details['away_goals_streak'] == 3
        assert opportunity.details['expected_outcome'] == 'high-scoring match (over 2.5 goals)'

    def test_rule_both_teams_good_form_insufficient_conditions(self, betting_engine, mock_match):
        """Test both teams good form rule with insufficient conditions"""
        # Mock team analysis - one team not in good form
        home_analysis = {
            'team': mock_match.home_team,
            'consecutive_wins': 1,  # Not enough wins
            'consecutive_losses': 0,
            'consecutive_draws': 0,
            'consecutive_no_goals': 0,
            'consecutive_goals': 2,
            'win_rate': 0.4,  # Not good enough
            'is_top_team': False,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_wins': 2,  # Good form
            'consecutive_losses': 0,
            'consecutive_draws': 0,
            'consecutive_no_goals': 0,
            'consecutive_goals': 3,  # Scoring consistently
            'win_rate': 0.65,  # Good win rate
            'is_top_team': False,
        }

        opportunity = betting_engine._rule_both_teams_good_form(
            mock_match, home_analysis, away_analysis
        )

        assert opportunity is None

    def test_enhanced_rule_strong_vs_weak_poor_form(self, betting_engine, mock_match):
        """Test enhanced strong vs weak poor form rule with multiple factors"""
        # Mock team analysis with multiple poor form indicators
        home_analysis = {
            'team': mock_match.home_team,
            'consecutive_losses': 4,  # Very poor form
            'consecutive_no_goals': 3,  # Not scoring
            'win_rate': 0.2,  # Very low win rate
            'consecutive_wins': 0,
            'consecutive_draws': 0,
            'consecutive_goals': 0,
            'is_top_team': False,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_losses': 0,
            'consecutive_no_goals': 0,
            'win_rate': 0.8,  # Good win rate
            'consecutive_wins': 4,  # Good form
            'consecutive_draws': 0,
            'consecutive_goals': 4,
            'is_top_team': True,
        }

        # Mock strength difference (away team much stronger)
        with patch.object(betting_engine, '_calculate_team_strength_difference', return_value=-12):
            opportunity = betting_engine._rule_strong_vs_weak_poor_form(
                mock_match, home_analysis, away_analysis, -12
            )

            assert opportunity is not None
            assert opportunity.rule_name == 'Strong vs Weak Poor Form'
            assert opportunity.confidence >= 0.85  # Should be boosted by multiple factors
            assert opportunity.details['strong_team'] == mock_match.away_team.name
            assert opportunity.details['weak_team'] == mock_match.home_team.name
            assert opportunity.details['strength_difference'] == -12
            assert opportunity.details['strong_team_win_rate'] == 0.8
            assert opportunity.details['strong_team_consecutive_wins'] == 4
            assert opportunity.details['weak_team_consecutive_losses'] == 4
            assert opportunity.details['weak_team_consecutive_no_goals'] == 3
            assert opportunity.details['weak_team_win_rate'] == 0.2

    def test_enhanced_rule_both_teams_poor_form(self, betting_engine, mock_match):
        """Test enhanced both teams poor form rule with confidence calculation"""
        # Mock team analysis with multiple poor form indicators
        home_analysis = {
            'team': mock_match.home_team,
            'consecutive_losses': 4,  # Very poor
            'consecutive_no_goals': 3,  # Not scoring
            'win_rate': 0.15,  # Very low
            'consecutive_wins': 0,
            'consecutive_draws': 0,
            'consecutive_goals': 0,
            'is_top_team': False,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_losses': 3,  # Poor
            'consecutive_no_goals': 2,  # Not scoring
            'win_rate': 0.25,  # Low
            'consecutive_wins': 0,
            'consecutive_draws': 0,
            'consecutive_goals': 0,
            'is_top_team': False,
        }

        opportunity = betting_engine._rule_both_teams_poor_form(
            mock_match, home_analysis, away_analysis
        )

        assert opportunity is not None
        assert opportunity.rule_name == 'Both Teams Poor Form'
        # Confidence should be higher due to multiple poor indicators
        assert opportunity.confidence > 0.70
        assert opportunity.details['expected_outcome'] == 'draw'
        assert opportunity.details['home_consecutive_losses'] == 4
        assert opportunity.details['home_consecutive_no_goals'] == 3
        assert opportunity.details['home_win_rate'] == 0.15
        assert opportunity.details['away_consecutive_losses'] == 3
        assert opportunity.details['away_consecutive_no_goals'] == 2
        assert opportunity.details['away_win_rate'] == 0.25

    def test_enhanced_rule_top_team_losing_vs_strong(self, betting_engine, mock_match):
        """Test enhanced top team losing vs strong rule with confidence boosts"""
        # Mock team analysis with multiple factors
        home_analysis = {
            'team': mock_match.home_team,
            'consecutive_losses': 5,  # Long losing streak
            'consecutive_no_goals': 3,  # Not scoring
            'consecutive_wins': 0,
            'consecutive_draws': 0,
            'consecutive_goals': 0,
            'is_top_team': True,
            'is_top5_team': True,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_losses': 0,
            'consecutive_no_goals': 0,
            'consecutive_wins': 3,  # Good form
            'consecutive_draws': 0,
            'consecutive_goals': 3,
            'is_top_team': False,
            'is_top5_team': False,
        }

        # Set up opponent rank to be within 5 ranks (strong opponent)
        mock_match.home_team.rank = 3
        mock_match.away_team.rank = 6  # Within 5 ranks (3 + 5 = 8, 6 <= 8)

        opportunity = betting_engine._rule_top_team_losing_vs_strong(
            mock_match, home_analysis, away_analysis, 3
        )

        assert opportunity is not None
        assert opportunity.rule_name == 'Top Team Losing vs Strong'
        # Confidence should be boosted by multiple factors
        assert opportunity.confidence >= 0.80
        assert opportunity.details['top_team'] == mock_match.home_team.name
        assert opportunity.details['opponent'] == mock_match.away_team.name
        assert opportunity.details['consecutive_losses'] == 5
        assert opportunity.details['consecutive_no_goals'] == 3
        assert opportunity.details['opponent_consecutive_wins'] == 3

    def test_enhanced_rule_top_team_drawing_streak(self, betting_engine, mock_match):
        """Test enhanced top team drawing streak rule with confidence boosts"""
        # Mock team analysis with multiple factors
        home_analysis = {
            'team': mock_match.home_team,
            'consecutive_draws': 5,  # Long drawing streak
            'consecutive_no_goals': 2,  # Not scoring
            'consecutive_wins': 0,
            'consecutive_losses': 0,
            'consecutive_goals': 0,
            'is_top_team': True,
            'is_top5_team': True,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_draws': 0,
            'consecutive_no_goals': 0,
            'consecutive_wins': 0,
            'consecutive_losses': 0,
            'consecutive_goals': 0,
            'is_top_team': False,
            'is_top5_team': False,
        }

        opportunity = betting_engine._rule_top_team_drawing_streak(
            mock_match, home_analysis, away_analysis
        )

        assert opportunity is not None
        assert opportunity.rule_name == 'Top Team Drawing Streak'
        # Confidence should be boosted by multiple factors
        assert opportunity.confidence >= 0.75
        assert opportunity.details['top_team'] == mock_match.home_team.name
        assert opportunity.details['consecutive_draws'] == 5
        assert opportunity.details['consecutive_no_goals'] == 2
        assert opportunity.details['expected_outcome'] == 'draw'

    def test_enhanced_rule_top_team_no_goals_vs_strong(self, betting_engine, mock_match):
        """Test enhanced top team no goals vs strong rule with confidence boosts"""
        # Mock team analysis with multiple factors
        home_analysis = {
            'team': mock_match.home_team,
            'consecutive_no_goals': 5,  # Long no-goals streak
            'consecutive_losses': 3,  # Also losing
            'consecutive_wins': 0,
            'consecutive_draws': 0,
            'consecutive_goals': 0,
            'is_top_team': True,
            'is_top5_team': True,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_no_goals': 0,
            'consecutive_losses': 0,
            'consecutive_wins': 4,  # Good form
            'consecutive_draws': 0,
            'consecutive_goals': 4,
            'is_top_team': False,
            'is_top5_team': False,
        }

        # Set up opponent rank to be within 8 ranks (strong opponent)
        mock_match.home_team.rank = 2
        mock_match.away_team.rank = 8  # Within 8 ranks (2 + 8 = 10, 8 <= 10)

        opportunity = betting_engine._rule_top_team_no_goals_vs_strong(
            mock_match, home_analysis, away_analysis, 6
        )

        assert opportunity is not None
        assert opportunity.rule_name == 'Top Team No Goals vs Strong'
        # Confidence should be boosted by multiple factors
        assert opportunity.confidence >= 0.80
        assert opportunity.details['top_team'] == mock_match.home_team.name
        assert opportunity.details['opponent'] == mock_match.away_team.name
        assert opportunity.details['consecutive_no_goals'] == 5
        assert opportunity.details['consecutive_losses'] == 3
        assert opportunity.details['opponent_consecutive_wins'] == 4

    def test_rule_confidence_calculation_edge_cases(self, betting_engine, mock_match):
        """Test confidence calculation edge cases"""
        # Test maximum confidence cap
        home_analysis = {
            'team': mock_match.home_team,
            'consecutive_losses': 6,  # Very long losing streak
            'consecutive_no_goals': 5,  # Very long no-goals streak
            'win_rate': 0.1,  # Very low win rate
            'consecutive_wins': 0,
            'consecutive_draws': 0,
            'consecutive_goals': 0,
            'is_top_team': False,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_losses': 0,
            'consecutive_no_goals': 0,
            'win_rate': 0.9,  # Very high win rate
            'consecutive_wins': 6,  # Very long winning streak
            'consecutive_draws': 0,
            'consecutive_goals': 6,
            'is_top_team': True,
        }

        # Mock very large strength difference
        with patch.object(betting_engine, '_calculate_team_strength_difference', return_value=-15):
            opportunity = betting_engine._rule_strong_vs_weak_poor_form(
                mock_match, home_analysis, away_analysis, -15
            )

            assert opportunity is not None
            # Confidence should be capped at 0.90
            assert opportunity.confidence == 0.90

    def test_analyze_team_performance_with_no_matches(self, betting_engine, mock_teams):
        """Test team performance analysis when no recent matches exist"""
        home_team, _ = mock_teams

        with patch.object(betting_engine, '_get_recent_matches') as mock_get_matches:
            mock_get_matches.return_value = []

            analysis = betting_engine._analyze_team_performance(home_team, 'home')

            # Should return default values when no matches exist
            assert analysis['consecutive_wins'] == 0
            assert analysis['consecutive_losses'] == 0
            assert analysis['consecutive_draws'] == 0
            assert analysis['consecutive_no_goals'] == 0
            assert analysis['consecutive_goals'] == 0
            assert analysis['total_matches'] == 0
            assert analysis['wins'] == 0
            assert analysis['draws'] == 0
            assert analysis['losses'] == 0
            assert analysis['win_rate'] == 0
            assert analysis['draw_rate'] == 0
            assert analysis['loss_rate'] == 0

    def test_analyze_team_performance_with_single_match(self, betting_engine, mock_teams):
        """Test team performance analysis with only one recent match"""
        home_team, _ = mock_teams

        with patch.object(betting_engine, '_get_recent_matches') as mock_get_matches:
            # Single match - home team wins
            match = Mock(spec=Match)
            match.home_team = home_team
            match.away_team = Mock(spec=Team)
            match.home_score = 2
            match.away_score = 0

            mock_get_matches.return_value = [match]

            analysis = betting_engine._analyze_team_performance(home_team, 'home')

            assert analysis['total_matches'] == 1
            assert analysis['wins'] == 1
            assert analysis['draws'] == 0
            assert analysis['losses'] == 0
            assert analysis['win_rate'] == 1.0
            assert analysis['draw_rate'] == 0.0
            assert analysis['loss_rate'] == 0.0
            assert analysis['consecutive_wins'] == 1
            assert analysis['consecutive_losses'] == 0
            assert analysis['consecutive_draws'] == 0
            assert analysis['consecutive_no_goals'] == 0
            assert analysis['consecutive_goals'] == 1

    def test_rule_strong_vs_weak_poor_form(self, betting_engine, mock_match):
        """Test strong vs weak poor form rule"""
        # Mock team analysis - away team is strong, home team is weak with poor form
        home_analysis = {
            'team': mock_match.home_team,
            'consecutive_losses': 3,  # Home team has poor form
            'consecutive_no_goals': 2,
            'consecutive_wins': 0,
            'consecutive_draws': 0,
            'consecutive_goals': 0,
            'win_rate': 0.2,
            'is_top_team': False,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_losses': 0,  # Away team is strong
            'consecutive_no_goals': 0,
            'consecutive_wins': 3,
            'consecutive_draws': 0,
            'consecutive_goals': 3,
            'win_rate': 0.8,
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
            'consecutive_wins': 0,
            'consecutive_draws': 0,
            'consecutive_goals': 0,
            'win_rate': 0.25,
            'is_top_team': False,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_losses': 3,
            'consecutive_no_goals': 2,
            'consecutive_wins': 0,
            'consecutive_draws': 0,
            'consecutive_goals': 0,
            'win_rate': 0.2,
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
            'consecutive_wins': 0,
            'consecutive_draws': 0,
            'consecutive_goals': 0,
            'is_top_team': True,
            'is_top5_team': True,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_losses': 0,
            'consecutive_no_goals': 0,
            'consecutive_wins': 2,
            'consecutive_draws': 0,
            'consecutive_goals': 2,
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
        home_analysis = {
            'team': mock_match.home_team,
            'consecutive_draws': 3,
            'consecutive_no_goals': 1,
            'consecutive_wins': 0,
            'consecutive_losses': 0,
            'consecutive_goals': 0,
            'is_top_team': True,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_draws': 0,
            'consecutive_no_goals': 0,
            'consecutive_wins': 0,
            'consecutive_losses': 0,
            'consecutive_goals': 0,
            'is_top_team': False,
        }

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
            'consecutive_wins': 0,
            'consecutive_losses': 0,
            'consecutive_draws': 0,
            'consecutive_goals': 0,
            'is_top_team': True,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_no_goals': 0,
            'consecutive_wins': 2,
            'consecutive_losses': 0,
            'consecutive_draws': 0,
            'consecutive_goals': 2,
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
            'consecutive_wins': 0,
            'consecutive_draws': 0,
            'consecutive_goals': 0,
            'win_rate': 0.2,
            'is_top_team': False,
        }
        away_analysis = {
            'team': mock_match.away_team,
            'consecutive_losses': 0,  # Away team is strong
            'consecutive_no_goals': 0,
            'consecutive_wins': 3,
            'consecutive_draws': 0,
            'consecutive_goals': 3,
            'win_rate': 0.8,
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

    @pytest.mark.parametrize(
        'rank,expected_is_top',
        [
            (1, True),  # Rank 1 should be top team
            (3, True),  # Rank 3 (Ajax) should be top team
            (8, True),  # Rank 8 should be top team (boundary)
            (9, False),  # Rank 9 (FC Volendam) should NOT be top team
            (10, False),  # Rank 10 should NOT be top team
            (15, False),  # Rank 15 should NOT be top team
        ],
    )
    def test_top_team_classification(self, betting_engine, rank, expected_is_top):
        """Test that team rank classification works correctly with top_teams_count=8"""
        is_top_team = rank <= betting_engine.top_teams_count
        assert is_top_team == expected_is_top, (
            f'Rank {rank} should {"be" if expected_is_top else "NOT be"} a top team'
        )


if __name__ == '__main__':
    pytest.main([__file__])
