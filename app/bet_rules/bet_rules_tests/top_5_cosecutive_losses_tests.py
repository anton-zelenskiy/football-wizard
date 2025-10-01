from app.bet_rules.structures import (
    BetOutcome,
    BetType,
    MatchSummary,
    Top5ConsecutiveLossesRule,
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


def test_top5_consecutive_losses_rule_creation():
    """Test creating Top5ConsecutiveLossesRule"""
    rule = Top5ConsecutiveLossesRule()
    assert rule.name == 'Top 5 Consecutive Losses Rule'
    assert rule.bet_type == BetType.DRAW_OR_WIN
    assert rule.base_confidence == 0.5


def test_top5_consecutive_losses_rule_not_top_5():
    """Test confidence calculation for non-top 5 team"""
    rule = Top5ConsecutiveLossesRule()
    team_analysis = create_team_analysis(consecutive_losses=3)

    confidence = rule.calculate_confidence(team_analysis)
    assert confidence == 0.0


def test_top5_consecutive_losses_rule_insufficient_losses():
    """Test confidence calculation with insufficient consecutive losses"""
    rule = Top5ConsecutiveLossesRule()
    team_analysis = create_team_analysis(consecutive_losses=1, rank=3)  # Less than 2

    confidence = rule.calculate_confidence(team_analysis)
    assert confidence == 0.0


def test_top5_consecutive_losses_rule_valid():
    """Test confidence calculation for valid top 5 team with losses"""
    rule = Top5ConsecutiveLossesRule()
    team_analysis = create_team_analysis(
        consecutive_losses=2, rank=3, consecutive_no_goals=0
    )

    confidence = rule.calculate_confidence(team_analysis)
    assert confidence == 0.7  # Base + 0.2 for top 5


def test_top5_consecutive_losses_rule_determine_outcome():
    """Test Top5ConsecutiveLossesRule determine_outcome method"""
    rule = Top5ConsecutiveLossesRule()

    # Home team (top-5) with consecutive losses - should win if home wins or draws
    match_result = MatchSummary(
        match_id=None,
        home_team='Home Team',
        away_team='Away Team',
        league='Test League',
        country='Test Country',
        match_date=None,
        home_score=2,
        away_score=1,
    )
    assert rule.determine_outcome(match_result, 'Home Team') == BetOutcome.WIN.value

    match_result = MatchSummary(
        match_id=None,
        home_team='Home Team',
        away_team='Away Team',
        league='Test League',
        country='Test Country',
        match_date=None,
        home_score=1,
        away_score=1,
    )
    assert rule.determine_outcome(match_result, 'Home Team') == BetOutcome.WIN.value

    match_result = MatchSummary(
        match_id=None,
        home_team='Home Team',
        away_team='Away Team',
        league='Test League',
        country='Test Country',
        match_date=None,
        home_score=1,
        away_score=2,
    )
    assert rule.determine_outcome(match_result, 'Home Team') == BetOutcome.LOSE.value

    # Away team (top-5) with consecutive losses - should win if away wins or draws
    match_result = MatchSummary(
        match_id=None,
        home_team='Home Team',
        away_team='Away Team',
        league='Test League',
        country='Test Country',
        match_date=None,
        home_score=1,
        away_score=2,
    )
    assert rule.determine_outcome(match_result, 'Away Team') == BetOutcome.WIN.value

    match_result = MatchSummary(
        match_id=None,
        home_team='Home Team',
        away_team='Away Team',
        league='Test League',
        country='Test Country',
        match_date=None,
        home_score=1,
        away_score=1,
    )
    assert rule.determine_outcome(match_result, 'Away Team') == BetOutcome.WIN.value

    match_result = MatchSummary(
        match_id=None,
        home_team='Home Team',
        away_team='Away Team',
        league='Test League',
        country='Test Country',
        match_date=None,
        home_score=2,
        away_score=1,
    )
    assert rule.determine_outcome(match_result, 'Away Team') == BetOutcome.LOSE.value

    # Both teams fit rule - should win if draw
    match_result = MatchSummary(
        match_id=None,
        home_team='Home Team',
        away_team='Away Team',
        league='Test League',
        country='Test Country',
        match_date=None,
        home_score=1,
        away_score=1,
    )
    assert rule.determine_outcome(match_result, 'Home Team') == BetOutcome.WIN.value

    match_result = MatchSummary(
        match_id=None,
        home_team='Home Team',
        away_team='Away Team',
        league='Test League',
        country='Test Country',
        match_date=None,
        home_score=2,
        away_score=1,
    )
    assert rule.determine_outcome(match_result, 'Home Team') == BetOutcome.WIN.value

    match_result = MatchSummary(
        match_id=None,
        home_team='Home Team',
        away_team='Away Team',
        league='Test League',
        country='Test Country',
        match_date=None,
        home_score=1,
        away_score=2,
    )
    assert rule.determine_outcome(match_result, 'Home Team') == BetOutcome.LOSE.value
