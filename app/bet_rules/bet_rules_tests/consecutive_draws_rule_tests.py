import pytest

from app.bet_rules.structures import (
    BetOutcome,
    BetType,
    ConsecutiveDrawsRule,
    MatchSummary,
)
from app.bet_rules.team_analysis import TeamAnalysis, TeamData


def create_team_analysis(
    consecutive_losses=0,
    consecutive_draws=0,
    consecutive_wins=0,
    consecutive_no_goals=0,
    rank=15,
    recent_matches=None,
):
    """Helper function to create TeamAnalysis"""
    team = TeamData(id=1, name='Test Team', rank=rank)

    analysis = TeamAnalysis(
        team=team,
        rank=rank,
        consecutive_losses=consecutive_losses,
        consecutive_draws=consecutive_draws,
        consecutive_wins=consecutive_wins,
        consecutive_no_goals=consecutive_no_goals,
        recent_matches=recent_matches or [],
    )

    return analysis


def test_consecutive_draws_rule_creation():
    """Test creating ConsecutiveDrawsRule"""
    rule = ConsecutiveDrawsRule()
    assert rule.name == 'Consecutive Draws Rule'
    assert rule.bet_type == BetType.WIN_OR_LOSE
    assert rule.base_confidence == 0.5


@pytest.mark.parametrize(
    'consecutive_draws,expected_confidence,description',
    [
        (2, 0.0, 'Less than 3 consecutive draws'),
        (3, 0.5, 'Basic 3 consecutive draws'),
        (4, 0.5, '4 consecutive draws'),
        (5, 0.5, '5 consecutive draws'),
    ],
)
def test_consecutive_draws_rule_confidence(
    consecutive_draws, expected_confidence, description
):
    """Test confidence calculation for consecutive draws rule"""
    rule = ConsecutiveDrawsRule()
    team_analysis = create_team_analysis(consecutive_draws=consecutive_draws)
    opponent_analysis = create_team_analysis(rank=10)
    match_summary = MatchSummary(
        home_team='Home Team',
        away_team='Away Team',
        league='Test League',
        country='Test Country',
    )

    confidence = rule.calculate_confidence(
        team_analysis, opponent_analysis, match_summary
    )
    assert (
        abs(confidence - expected_confidence) < 0.001
    ), f'Failed for {description}: got {confidence}, expected {expected_confidence}'


@pytest.mark.parametrize(
    'home_score,away_score,team_analyzed,expected_outcome,description',
    [
        (2, 1, 'Home Team', BetOutcome.WIN, 'Home team wins'),
        (1, 1, 'Home Team', BetOutcome.LOSE, 'Home team draws'),
        (1, 2, 'Home Team', BetOutcome.WIN, 'Home team loses'),
        (1, 2, 'Away Team', BetOutcome.WIN, 'Away team wins'),
        (1, 1, 'Away Team', BetOutcome.LOSE, 'Away team draws'),
        (2, 1, 'Away Team', BetOutcome.WIN, 'Away team loses'),
    ],
)
def test_consecutive_draws_rule_determine_outcome(
    home_score, away_score, team_analyzed, expected_outcome, description
):
    """Test ConsecutiveDrawsRule determine_outcome method"""
    rule = ConsecutiveDrawsRule()

    match_result = MatchSummary(
        match_id=None,
        home_team='Home Team',
        away_team='Away Team',
        league='Test League',
        country='Test Country',
        match_date=None,
        home_score=home_score,
        away_score=away_score,
    )

    outcome = rule.determine_outcome(match_result, team_analyzed)
    assert outcome == expected_outcome, f'Failed for {description}'
