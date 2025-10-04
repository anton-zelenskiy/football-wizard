import pytest

from app.bet_rules.structures import (
    BetOutcome,
    BetType,
    ConsecutiveLossesRule,
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


def test_consecutive_losses_rule_creation():
    """Test creating ConsecutiveLossesRule"""
    rule = ConsecutiveLossesRule()
    assert rule.name == 'Consecutive Losses Rule'
    assert rule.bet_type == BetType.DRAW_OR_WIN
    assert rule.base_confidence == 0.5


@pytest.mark.parametrize(
    'consecutive_losses,expected_confidence,description',
    [
        (2, 0.0, 'Less than 3 consecutive losses'),
        (3, 0.5, 'Basic 3 consecutive losses'),
        (4, 0.5, '4 consecutive losses'),
        (5, 0.5, '5 consecutive losses'),
    ],
)
def test_consecutive_losses_rule_confidence(
    consecutive_losses, expected_confidence, description
):
    """Test confidence calculation for consecutive losses rule"""
    rule = ConsecutiveLossesRule()
    team_analysis = create_team_analysis(consecutive_losses=consecutive_losses)
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
    assert confidence == expected_confidence, f'Failed for {description}'


@pytest.mark.parametrize(
    'rank,opponent_rank,expected_confidence,description',
    [
        (15, 10, 0.5, 'Regular team (rank 15) vs rank 10'),
        (
            8,
            10,
            0.65,
            'Top 10 team (rank 8) vs rank 10',
        ),  # 0.5 + 0.1 + 0.05 (rank diff)
        (
            3,
            10,
            0.875,
            'Top 5 team (rank 3) vs rank 10',
        ),  # 0.5 + 0.2 + 0.175 (rank diff)
        (1, 10, 0.925, 'Top team (rank 1) vs rank 10'),  # 0.5 + 0.2 + 0.225 (rank diff)
    ],
)
def test_consecutive_losses_rule_rank_bonus(
    rank, opponent_rank, expected_confidence, description
):
    """Test confidence calculation with rank bonuses"""
    rule = ConsecutiveLossesRule()
    team_analysis = create_team_analysis(consecutive_losses=3, rank=rank)
    opponent_analysis = create_team_analysis(rank=opponent_rank)
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
    'consecutive_no_goals,expected_confidence,description',
    [
        (0, 0.5, 'No no-goals streak'),
        (2, 0.55, '2 consecutive no-goals'),
        (3, 0.6, '3 consecutive no-goals'),
        (4, 0.65, '4 consecutive no-goals'),
        (5, 0.7, '5 consecutive no-goals'),
        (6, 0.7, '6+ consecutive no-goals (capped)'),
    ],
)
def test_consecutive_losses_rule_no_goals_bonus(
    consecutive_no_goals, expected_confidence, description
):
    """Test confidence calculation with no-goals streak bonuses"""
    rule = ConsecutiveLossesRule()
    team_analysis = create_team_analysis(
        consecutive_losses=3, consecutive_no_goals=consecutive_no_goals
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
def test_consecutive_losses_rule_determine_outcome(
    home_score, away_score, team_analyzed, expected_outcome, description
):
    """Test ConsecutiveLossesRule determine_outcome method"""
    rule = ConsecutiveLossesRule()

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
