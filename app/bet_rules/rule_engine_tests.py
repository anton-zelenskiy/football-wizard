from datetime import datetime
from unittest.mock import Mock, patch

from app.bet_rules.rule_engine import BettingRulesEngine
from app.bet_rules.structures import (
    BetType,
    ConsecutiveDrawsRule,
    ConsecutiveLossesRule,
)
from app.bet_rules.team_analysis import TeamAnalysis
from app.db.models import League, Match, Team


def create_mock_team_analysis(
    consecutive_losses=0,
    consecutive_draws=0,
    consecutive_wins=0,
    consecutive_no_goals=0,
    rank=15,
    recent_matches=None,
):
    """Helper function to create mock TeamAnalysis"""
    team = Mock(spec=Team)
    team.name = 'Test Team'
    team.rank = rank

    analysis = Mock(spec=TeamAnalysis)
    analysis.team = team
    analysis.rank = rank
    analysis.consecutive_losses = consecutive_losses
    analysis.consecutive_draws = consecutive_draws
    analysis.consecutive_wins = consecutive_wins
    analysis.consecutive_no_goals = consecutive_no_goals
    analysis.recent_matches = recent_matches or []

    # Mock the computed properties
    analysis.is_top_team = rank <= 8
    analysis.is_top5_team = rank <= 5

    return analysis


def create_mock_match():
    """Helper function to create mock Match"""
    home_team = Mock(spec=Team)
    home_team.name = 'Home Team'
    home_team.rank = 3

    away_team = Mock(spec=Team)
    away_team.name = 'Away Team'
    away_team.rank = 10

    league = Mock(spec=League)
    league.name = 'Test League'
    league.country = 'Test Country'

    match = Mock(spec=Match)
    match.id = 123
    match.home_team = home_team
    match.away_team = away_team
    match.league = league
    match.match_date = datetime(2025, 1, 1, 15, 0, 0)

    return match


@patch('app.bet_rules.rule_engine.FootballDataStorage')
def test_analyze_scheduled_matches_no_matches(mock_storage):
    """Test analyze_scheduled_matches with no matches"""
    mock_storage.return_value.get_scheduled_matches.return_value = []

    engine = BettingRulesEngine()
    opportunities = engine.analyze_scheduled_matches()

    assert opportunities == []


@patch('app.bet_rules.rule_engine.FootballDataStorage')
def test_analyze_scheduled_matches_single_team_fits_rule(mock_storage):
    """Test analyze_scheduled_matches with one team fitting a rule"""
    match = create_mock_match()
    mock_storage.return_value.get_scheduled_matches.return_value = [match]
    mock_storage.return_value.get_team_recent_finished_matches.return_value = []

    # Mock team analysis service
    with patch('app.bet_rules.rule_engine.TeamAnalysisService') as mock_service:
        mock_analyzer = Mock()
        mock_service.return_value = mock_analyzer

        # Home team fits consecutive losses rule (but not top5 rule - rank 6)
        home_analysis = create_mock_team_analysis(consecutive_losses=3, rank=6)
        # Away team doesn't fit any rule
        away_analysis = create_mock_team_analysis(consecutive_losses=1, rank=10)

        mock_analyzer.analyze_team_performance.side_effect = [
            home_analysis,
            away_analysis,
        ]

        engine = BettingRulesEngine()
        opportunities = engine.analyze_scheduled_matches()

        assert len(opportunities) == 1
        opportunity = opportunities[0]
        assert opportunity.match_id == 123
        assert opportunity.home_team == 'Home Team'
        assert opportunity.away_team == 'Away Team'
        assert opportunity.rule_name == 'Consecutive Losses Rule'
        assert opportunity.bet_type == BetType.DRAW_OR_WIN
        assert opportunity.team_analyzed == 'Home Team'
        assert opportunity.details['home_team_fits'] is True
        assert opportunity.details['away_team_fits'] is False
        assert opportunity.details['both_teams_fit'] is False


@patch('app.bet_rules.rule_engine.FootballDataStorage')
def test_analyze_scheduled_matches_both_teams_fit_same_rule(mock_storage):
    """Test analyze_scheduled_matches with both teams fitting the same rule"""
    match = create_mock_match()
    mock_storage.return_value.get_scheduled_matches.return_value = [match]
    mock_storage.return_value.get_team_recent_finished_matches.return_value = []

    # Mock team analysis service
    with patch('app.bet_rules.rule_engine.TeamAnalysisService') as mock_service:
        mock_analyzer = Mock()
        mock_service.return_value = mock_analyzer

        # Both teams fit consecutive draws rule
        home_analysis = create_mock_team_analysis(consecutive_draws=3, rank=5)
        away_analysis = create_mock_team_analysis(consecutive_draws=3, rank=8)

        mock_analyzer.analyze_team_performance.side_effect = [
            home_analysis,
            away_analysis,
        ]

        engine = BettingRulesEngine()
        opportunities = engine.analyze_scheduled_matches()

        assert len(opportunities) == 1
        opportunity = opportunities[0]
        assert opportunity.match_id == 123
        assert opportunity.home_team == 'Home Team'
        assert opportunity.away_team == 'Away Team'
        assert opportunity.rule_name == 'Consecutive Draws Rule'
        assert opportunity.bet_type == BetType.WIN_OR_LOSE
        # With new logic, should pick the team with higher confidence
        # Home team (rank 5) should have higher confidence than away team (rank 8)
        assert opportunity.team_analyzed == 'Home Team'
        assert opportunity.details['home_team_fits'] is True
        assert opportunity.details['away_team_fits'] is True
        assert opportunity.details['both_teams_fit'] is True
        assert 'uncertainty_note' not in opportunity.details


def test_check_rule_for_match_single_team_fits():
    """Test _check_rule_for_match when only one team fits the rule"""
    match = create_mock_match()
    rule = ConsecutiveLossesRule()

    # Only home team has consecutive losses
    home_analysis = create_mock_team_analysis(consecutive_losses=3, rank=3)
    away_analysis = create_mock_team_analysis(consecutive_losses=1, rank=8)

    engine = BettingRulesEngine()
    opportunity = engine._check_rule_for_match(
        match, rule, home_analysis, away_analysis
    )

    assert opportunity is not None
    assert opportunity.team_analyzed == 'Home Team'
    assert opportunity.details['home_team_fits'] is True
    assert opportunity.details['away_team_fits'] is False
    assert opportunity.details['both_teams_fit'] is False
    assert 'uncertainty_note' not in opportunity.details


def test_check_rule_for_match_both_teams_fit():
    """Test _check_rule_for_match when both teams fit the rule"""
    match = create_mock_match()
    rule = ConsecutiveDrawsRule()

    # Both teams have consecutive draws
    home_analysis = create_mock_team_analysis(consecutive_draws=3, rank=5)
    away_analysis = create_mock_team_analysis(consecutive_draws=3, rank=8)

    engine = BettingRulesEngine()
    opportunity = engine._check_rule_for_match(
        match, rule, home_analysis, away_analysis
    )

    assert opportunity is not None
    # With new logic, should pick the team with higher confidence
    # Home team (rank 5) should have higher confidence than away team (rank 8)
    assert opportunity.team_analyzed == 'Home Team'
    assert opportunity.details['home_team_fits'] is True
    assert opportunity.details['away_team_fits'] is True
    assert opportunity.details['both_teams_fit'] is True
    assert 'uncertainty_note' not in opportunity.details
