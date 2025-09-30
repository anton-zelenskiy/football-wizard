from app.bet_rules.structures import (
    BetOutcome,
    BetType,
    ConsecutiveDrawsRule,
    MatchResult,
)
from app.bet_rules.team_analysis import TeamAnalysis
from app.db.models import Team


def create_team_analysis(
    consecutive_losses=0,
    consecutive_draws=0,
    consecutive_wins=0,
    consecutive_no_goals=0,
    rank=15,
    recent_matches=None,
):
    """Helper function to create TeamAnalysis"""
    team = Team()
    team.name = 'Test Team'
    team.rank = rank

    analysis = TeamAnalysis(
        team=team,
        team_type='home',
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


def test_consecutive_draws_rule_no_draws():
    """Test confidence calculation with no consecutive draws"""
    rule = ConsecutiveDrawsRule()
    team_analysis = create_team_analysis(consecutive_draws=2)  # Less than 3

    confidence = rule.calculate_confidence(team_analysis)
    assert confidence == 0.0


def test_consecutive_draws_rule_basic():
    """Test basic confidence calculation"""
    rule = ConsecutiveDrawsRule()
    team_analysis = create_team_analysis(consecutive_draws=3)

    confidence = rule.calculate_confidence(team_analysis)
    assert confidence == 0.5  # Base confidence only


def test_consecutive_draws_rule_determine_outcome():
    """Test ConsecutiveDrawsRule determine_outcome method"""
    rule = ConsecutiveDrawsRule()

    # Home team with consecutive draws - win_or_lose bet: win if home wins OR loses (not draw)
    match_result = MatchResult(
        home_score=2,
        away_score=1,
        home_team='Home Team',
        away_team='Away Team',
        team_analyzed='Home Team',
    )
    assert rule.determine_outcome(match_result) == BetOutcome.WIN.value

    # Draw should be LOSE for win_or_lose bet
    match_result = MatchResult(
        home_score=1,
        away_score=1,
        home_team='Home Team',
        away_team='Away Team',
        team_analyzed='Home Team',
    )
    assert rule.determine_outcome(match_result) == BetOutcome.LOSE.value

    # Home team loses should be WIN for win_or_lose bet (not a draw)
    match_result = MatchResult(
        home_score=1,
        away_score=2,
        home_team='Home Team',
        away_team='Away Team',
        team_analyzed='Home Team',
    )
    assert rule.determine_outcome(match_result) == BetOutcome.WIN.value

    # Away team with consecutive draws - win_or_lose bet: win if away wins OR loses (not draw)
    match_result = MatchResult(
        home_score=1,
        away_score=2,
        home_team='Home Team',
        away_team='Away Team',
        team_analyzed='Away Team',
    )
    assert rule.determine_outcome(match_result) == BetOutcome.WIN.value

    # Draw should be LOSE for win_or_lose bet
    match_result = MatchResult(
        home_score=1,
        away_score=1,
        home_team='Home Team',
        away_team='Away Team',
        team_analyzed='Away Team',
    )
    assert rule.determine_outcome(match_result) == BetOutcome.LOSE.value

    # Away team loses should be WIN for win_or_lose bet (not a draw)
    match_result = MatchResult(
        home_score=2,
        away_score=1,
        home_team='Home Team',
        away_team='Away Team',
        team_analyzed='Away Team',
    )
    assert rule.determine_outcome(match_result) == BetOutcome.WIN.value

    # Both teams fit rule - should win if either team wins (not draw)
    match_result = MatchResult(
        home_score=2,
        away_score=1,
        home_team='Home Team',
        away_team='Away Team',
        team_analyzed='Both Teams',
    )
    assert rule.determine_outcome(match_result) == BetOutcome.WIN.value

    match_result = MatchResult(
        home_score=1,
        away_score=2,
        home_team='Home Team',
        away_team='Away Team',
        team_analyzed='Both Teams',
    )
    assert rule.determine_outcome(match_result) == BetOutcome.WIN.value

    # Draw should be LOSE for win_or_lose bet
    match_result = MatchResult(
        home_score=1,
        away_score=1,
        home_team='Home Team',
        away_team='Away Team',
        team_analyzed='Both Teams',
    )
    assert rule.determine_outcome(match_result) == BetOutcome.LOSE.value
