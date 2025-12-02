import pytest

from app.bet_rules.bet_rules import Top5ConsecutiveLossesRule
from app.bet_rules.structures import (
    BetOutcome,
    BetType,
    MatchSummary,
    TeamAnalysis,
    TeamData,
)


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


def test_top5_consecutive_losses_rule_creation():
    """Test creating Top5ConsecutiveLossesRule"""
    rule = Top5ConsecutiveLossesRule()
    assert rule.name == 'Top 5 Consecutive Losses Rule'
    assert rule.bet_type == BetType.DRAW_OR_WIN
    assert rule.base_confidence == 0.5


@pytest.mark.parametrize(
    'consecutive_losses,rank,expected_confidence,description',
    [
        (3, 10, 0.0, 'Non-top 5 team (rank 10)'),
        (1, 3, 0.0, 'Top 5 team with insufficient losses (1)'),
        (2, 3, 0.7, 'Valid top 5 team with 2 losses'),
        (3, 3, 0.7, 'Valid top 5 team with 3 losses'),
        (4, 3, 0.7, 'Valid top 5 team with 4 losses'),
    ],
)
def test_top5_consecutive_losses_rule_confidence(
    consecutive_losses, rank, expected_confidence, description
):
    """Test confidence calculation for top 5 consecutive losses rule"""
    rule = Top5ConsecutiveLossesRule()
    team_analysis = create_team_analysis(
        consecutive_losses=consecutive_losses, rank=rank
    )
    opponent_analysis = create_team_analysis(rank=10)
    match_summary = MatchSummary(
        home_team_data=TeamData(id=1, name='Home Team', rank=5),
        away_team_data=TeamData(id=2, name='Away Team', rank=10),
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
        (1, 1, 'Home Team', BetOutcome.WIN, 'Home team draws'),
        (1, 2, 'Home Team', BetOutcome.LOSE, 'Home team loses'),
        (1, 2, 'Away Team', BetOutcome.WIN, 'Away team wins'),
        (1, 1, 'Away Team', BetOutcome.WIN, 'Away team draws'),
        (2, 1, 'Away Team', BetOutcome.LOSE, 'Away team loses'),
    ],
)
def test_top5_consecutive_losses_rule_determine_outcome(
    home_score, away_score, team_analyzed, expected_outcome, description
):
    """Test Top5ConsecutiveLossesRule determine_outcome method"""
    rule = Top5ConsecutiveLossesRule()

    match_result = MatchSummary(
        match_id=None,
        home_team_data=TeamData(id=1, name='Home Team', rank=5),
        away_team_data=TeamData(id=2, name='Away Team', rank=10),
        league='Test League',
        country='Test Country',
        match_date=None,
        home_score=home_score,
        away_score=away_score,
    )

    outcome = rule.determine_outcome(match_result, team_analyzed)
    assert outcome == expected_outcome, f'Failed for {description}'
