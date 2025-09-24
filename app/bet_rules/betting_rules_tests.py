#!/usr/bin/env python3

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.db.models import League, Match, Team

from .betting_rules import BettingOpportunity, BettingRulesEngine
from .team_analysis import TeamAnalysis


def create_team_analysis_from_dict(team, team_type, analysis_dict):
    """Helper function to create TeamAnalysis from dictionary for testing"""
    # Calculate wins, draws, losses from win_rate if not provided
    total_matches = analysis_dict.get('total_matches', 100)  # Use 100 for better precision
    win_rate = analysis_dict.get('win_rate', 0.0)
    draw_rate = analysis_dict.get('draw_rate', 0.0)
    
    wins = int(total_matches * win_rate)
    draws = int(total_matches * draw_rate)
    losses = total_matches - wins - draws
    
    return TeamAnalysis(
        team=team,
        team_type=team_type,
        rank=analysis_dict.get('rank'),
        consecutive_wins=analysis_dict.get('consecutive_wins', 0),
        consecutive_losses=analysis_dict.get('consecutive_losses', 0),
        consecutive_draws=analysis_dict.get('consecutive_draws', 0),
        consecutive_no_goals=analysis_dict.get('consecutive_no_goals', 0),
        consecutive_goals=analysis_dict.get('consecutive_goals', 0),
        recent_matches=analysis_dict.get('recent_matches', []),
        total_matches=total_matches,
        wins=wins,
        draws=draws,
        losses=losses,
        is_top_team=analysis_dict.get('is_top_team', False),
        is_top5_team=analysis_dict.get('is_top5_team', False),
    )


@pytest.fixture
def betting_engine() -> BettingRulesEngine:
    """Create a BettingRulesEngine instance for testing"""
    return BettingRulesEngine()


@pytest.fixture
def mock_league() -> Mock:
    """Create a mock league for testing"""
    league = Mock(spec=League)
    league.name = 'Test League'
    league.country = 'Test Country'
    return league


@pytest.fixture
def mock_teams() -> tuple[Mock, Mock]:
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
def mock_match(mock_teams) -> Mock:
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
def mock_live_match(mock_teams) -> Mock:
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


def test_betting_engine_init(betting_engine) -> None:
        """Test BettingRulesEngine initialization"""
        assert betting_engine.storage is not None
        assert betting_engine.top_teams_count > 0
        assert betting_engine.min_consecutive_losses > 0
        assert betting_engine.min_consecutive_draws > 0
        assert betting_engine.min_consecutive_losses_top5 > 0
        assert betting_engine.min_no_goals_matches > 0
        assert betting_engine.live_draw_minute_threshold > 0


def test_calculate_team_strength_difference(betting_engine, mock_teams) -> None:
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


def test_rule_winning_streak_vs_losing_streak(betting_engine, mock_match) -> None:
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


def test_rule_winning_streak_vs_losing_streak_away_team(betting_engine, mock_match) -> None:
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


def test_rule_winning_streak_vs_losing_streak_insufficient_streaks(betting_engine, mock_match) -> None:
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


def test_rule_high_scoring_vs_low_scoring(betting_engine, mock_match) -> None:
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


def test_rule_both_teams_good_form(betting_engine, mock_match) -> None:
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


def test_rule_both_teams_good_form_insufficient_conditions(betting_engine, mock_match) -> None:
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


def test_enhanced_rule_strong_vs_weak_poor_form(betting_engine, mock_match) -> None:
    """Test enhanced strong vs weak poor form rule with multiple factors"""
    # Mock team analysis with multiple poor form indicators
    home_analysis_dict = {
        'team': mock_match.home_team,
        'consecutive_losses': 4,  # Very poor form
        'consecutive_no_goals': 3,  # Not scoring
        'win_rate': 0.2,  # Very low win rate
        'consecutive_wins': 0,
        'consecutive_draws': 0,
        'consecutive_goals': 0,
        'is_top_team': False,
    }
    away_analysis_dict = {
        'team': mock_match.away_team,
        'consecutive_losses': 0,
        'consecutive_no_goals': 0,
        'win_rate': 0.8,  # Good win rate
        'consecutive_wins': 4,  # Good form
        'consecutive_draws': 0,
        'consecutive_goals': 4,
        'is_top_team': True,
    }

    # Convert to TeamAnalysis objects
    home_analysis = create_team_analysis_from_dict(mock_match.home_team, 'home', home_analysis_dict)
    away_analysis = create_team_analysis_from_dict(mock_match.away_team, 'away', away_analysis_dict)

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


def test_enhanced_rule_both_teams_poor_form(betting_engine, mock_match) -> None:
    """Test enhanced both teams poor form rule with confidence calculation"""
    # Mock team analysis with multiple poor form indicators
    home_analysis_dict = {
        'team': mock_match.home_team,
        'consecutive_losses': 4,  # Very poor
        'consecutive_no_goals': 3,  # Not scoring
        'win_rate': 0.15,  # Very low
        'consecutive_wins': 0,
        'consecutive_draws': 0,
        'consecutive_goals': 0,
        'is_top_team': False,
    }
    away_analysis_dict = {
        'team': mock_match.away_team,
        'consecutive_losses': 3,  # Poor
        'consecutive_no_goals': 2,  # Not scoring
        'win_rate': 0.25,  # Low
        'consecutive_wins': 0,
        'consecutive_draws': 0,
        'consecutive_goals': 0,
        'is_top_team': False,
    }

    # Convert to TeamAnalysis objects
    home_analysis = create_team_analysis_from_dict(mock_match.home_team, 'home', home_analysis_dict)
    away_analysis = create_team_analysis_from_dict(mock_match.away_team, 'away', away_analysis_dict)

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


def test_rule_live_red_card_draw_second_half(betting_engine, mock_live_match) -> None:
    """Test live red card draw second half rule"""
    opportunity = betting_engine._rule_live_red_card_draw_second_half(mock_live_match)

    assert opportunity is not None
    assert opportunity.rule_name == 'Live Red Card Draw Second Half'
    assert opportunity.confidence > 0
    assert 'minute' in opportunity.details
    assert 'team_with_red' in opportunity.details
    assert 'team_against' in opportunity.details


def test_rule_live_draw_top5_vs_below(betting_engine, mock_live_match) -> None:
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


def test_analyze_scheduled_matches(betting_engine) -> None:
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


def test_analyze_live_matches(betting_engine) -> None:
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


def test_save_opportunity(betting_engine) -> None:
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

    with patch('app.bet_rules.betting_rules.BettingOpportunity') as mock_db_opportunity:
        mock_instance = Mock()
        mock_db_opportunity.return_value = mock_instance

        result = betting_engine.save_opportunity(opportunity)

        assert result == mock_instance
        mock_instance.save.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__])