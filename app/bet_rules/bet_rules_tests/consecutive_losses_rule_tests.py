from app.bet_rules.structures import (
    BetOutcome,
    BetType,
    ConsecutiveLossesRule,
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


def test_consecutive_losses_rule_creation():
    """Test creating ConsecutiveLossesRule"""
    rule = ConsecutiveLossesRule()
    assert rule.name == 'Consecutive Losses Rule'
    assert rule.bet_type == BetType.DRAW_OR_WIN
    assert rule.base_confidence == 0.5


def test_consecutive_losses_rule_no_losses():
    """Test confidence calculation with no consecutive losses"""
    rule = ConsecutiveLossesRule()
    team_analysis = create_team_analysis(consecutive_losses=2)  # Less than 3

    confidence = rule.calculate_confidence(team_analysis)
    assert confidence == 0.0


def test_consecutive_losses_rule_basic():
    """Test basic confidence calculation"""
    rule = ConsecutiveLossesRule()
    team_analysis = create_team_analysis(consecutive_losses=3)

    confidence = rule.calculate_confidence(team_analysis)
    assert confidence == 0.5  # Base confidence only


def test_consecutive_losses_rule_top_10():
    """Test confidence calculation for top 10 team"""
    rule = ConsecutiveLossesRule()
    team_analysis = create_team_analysis(consecutive_losses=3, rank=8)

    confidence = rule.calculate_confidence(team_analysis)
    assert confidence == 0.6  # Base + 0.1 for top 10


def test_consecutive_losses_rule_top_5():
    """Test confidence calculation for top 5 team"""
    rule = ConsecutiveLossesRule()
    team_analysis = create_team_analysis(consecutive_losses=3, rank=3)

    confidence = rule.calculate_confidence(team_analysis)
    assert confidence == 0.7  # Base + 0.2 for top 5


def test_consecutive_losses_rule_no_goals():
    """Test confidence calculation with no goals in last 2 matches"""
    rule = ConsecutiveLossesRule()
    team_analysis = create_team_analysis(consecutive_losses=3, consecutive_no_goals=2)

    confidence = rule.calculate_confidence(team_analysis)
    assert confidence == 0.55  # Base + 0.05 for no goals last 2


def test_consecutive_losses_rule_determine_outcome():
    """Test ConsecutiveLossesRule determine_outcome method"""
    rule = ConsecutiveLossesRule()

    # Home team with consecutive losses - should win if home wins or draws
    match_result = MatchResult(
        home_score=2,
        away_score=1,
        home_team='Home Team',
        away_team='Away Team',
        team_analyzed='Home Team',
    )
    assert rule.determine_outcome(match_result) == BetOutcome.WIN.value

    match_result = MatchResult(
        home_score=1,
        away_score=1,
        home_team='Home Team',
        away_team='Away Team',
        team_analyzed='Home Team',
    )
    assert rule.determine_outcome(match_result) == BetOutcome.WIN.value

    match_result = MatchResult(
        home_score=1,
        away_score=2,
        home_team='Home Team',
        away_team='Away Team',
        team_analyzed='Home Team',
    )
    assert rule.determine_outcome(match_result) == BetOutcome.LOSE.value

    # Away team with consecutive losses - should win if away wins or draws
    match_result = MatchResult(
        home_score=1,
        away_score=2,
        home_team='Home Team',
        away_team='Away Team',
        team_analyzed='Away Team',
    )
    assert rule.determine_outcome(match_result) == BetOutcome.WIN.value

    match_result = MatchResult(
        home_score=1,
        away_score=1,
        home_team='Home Team',
        away_team='Away Team',
        team_analyzed='Away Team',
    )
    assert rule.determine_outcome(match_result) == BetOutcome.WIN.value

    match_result = MatchResult(
        home_score=2,
        away_score=1,
        home_team='Home Team',
        away_team='Away Team',
        team_analyzed='Away Team',
    )
    assert rule.determine_outcome(match_result) == BetOutcome.LOSE.value

    # Both teams fit rule - should win if draw
    match_result = MatchResult(
        home_score=1,
        away_score=1,
        home_team='Home Team',
        away_team='Away Team',
        team_analyzed='Both Teams',
    )
    assert rule.determine_outcome(match_result) == BetOutcome.WIN.value

    match_result = MatchResult(
        home_score=2,
        away_score=1,
        home_team='Home Team',
        away_team='Away Team',
        team_analyzed='Both Teams',
    )
    assert rule.determine_outcome(match_result) == BetOutcome.LOSE.value

    match_result = MatchResult(
        home_score=1,
        away_score=2,
        home_team='Home Team',
        away_team='Away Team',
        team_analyzed='Both Teams',
    )
    assert rule.determine_outcome(match_result) == BetOutcome.LOSE.value
