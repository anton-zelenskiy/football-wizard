from unittest.mock import Mock

from pydantic import ValidationError
import pytest

from app.bet_rules.structures import (
    Bet,
    BetOutcome,
    BetType,
    ConsecutiveDrawsRule,
    ConsecutiveLossesRule,
    MatchResult,
    Top5ConsecutiveLossesRule,
)
from app.bet_rules.team_analysis import TeamAnalysis
from app.db.models import Team


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


def test_bet_type_values():
    """Test that BetType has correct values"""
    assert BetType.WIN == 'win'
    assert BetType.DRAW == 'draw'
    assert BetType.LOSE == 'lose'
    assert BetType.DRAW_OR_WIN == 'draw_or_win'
    assert BetType.WIN_OR_LOSE == 'win_or_lose'
    assert BetType.GOAL == 'goal'


def test_consecutive_losses_rule_creation():
    """Test creating ConsecutiveLossesRule"""
    rule = ConsecutiveLossesRule()
    assert rule.name == 'Consecutive Losses Rule'
    assert rule.bet_type == BetType.DRAW_OR_WIN
    assert rule.base_confidence == 0.5


def test_consecutive_losses_rule_no_losses():
    """Test confidence calculation with no consecutive losses"""
    rule = ConsecutiveLossesRule()
    team_analysis = create_mock_team_analysis(consecutive_losses=2)  # Less than 3

    confidence = rule.calculate_confidence(team_analysis)
    assert confidence == 0.0


def test_consecutive_losses_rule_basic():
    """Test basic confidence calculation"""
    rule = ConsecutiveLossesRule()
    team_analysis = create_mock_team_analysis(consecutive_losses=3)

    confidence = rule.calculate_confidence(team_analysis)
    assert confidence == 0.5  # Base confidence only


def test_consecutive_losses_rule_top_10():
    """Test confidence calculation for top 10 team"""
    rule = ConsecutiveLossesRule()
    team_analysis = create_mock_team_analysis(consecutive_losses=3, rank=8)

    confidence = rule.calculate_confidence(team_analysis)
    assert confidence == 0.6  # Base + 0.1 for top 10


def test_consecutive_losses_rule_top_5():
    """Test confidence calculation for top 5 team"""
    rule = ConsecutiveLossesRule()
    team_analysis = create_mock_team_analysis(consecutive_losses=3, rank=3)

    confidence = rule.calculate_confidence(team_analysis)
    assert confidence == 0.7  # Base + 0.2 for top 5


def test_consecutive_losses_rule_no_goals():
    """Test confidence calculation with no goals in last 2 matches"""
    rule = ConsecutiveLossesRule()
    team_analysis = create_mock_team_analysis(
        consecutive_losses=3, consecutive_no_goals=2
    )

    confidence = rule.calculate_confidence(team_analysis)
    assert confidence == 0.55  # Base + 0.05 for no goals last 2


def test_consecutive_draws_rule_creation():
    """Test creating ConsecutiveDrawsRule"""
    rule = ConsecutiveDrawsRule()
    assert rule.name == 'Consecutive Draws Rule'
    assert rule.bet_type == BetType.WIN_OR_LOSE
    assert rule.base_confidence == 0.5


def test_consecutive_draws_rule_no_draws():
    """Test confidence calculation with no consecutive draws"""
    rule = ConsecutiveDrawsRule()
    team_analysis = create_mock_team_analysis(consecutive_draws=2)  # Less than 3

    confidence = rule.calculate_confidence(team_analysis)
    assert confidence == 0.0


def test_consecutive_draws_rule_basic():
    """Test basic confidence calculation"""
    rule = ConsecutiveDrawsRule()
    team_analysis = create_mock_team_analysis(consecutive_draws=3)

    confidence = rule.calculate_confidence(team_analysis)
    assert confidence == 0.5  # Base confidence only


def test_top5_consecutive_losses_rule_creation():
    """Test creating Top5ConsecutiveLossesRule"""
    rule = Top5ConsecutiveLossesRule()
    assert rule.name == 'Top 5 Consecutive Losses Rule'
    assert rule.bet_type == BetType.DRAW_OR_WIN
    assert rule.base_confidence == 0.5


def test_top5_consecutive_losses_rule_not_top_5():
    """Test confidence calculation for non-top 5 team"""
    rule = Top5ConsecutiveLossesRule()
    team_analysis = create_mock_team_analysis(consecutive_losses=3)

    confidence = rule.calculate_confidence(team_analysis)
    assert confidence == 0.0


def test_top5_consecutive_losses_rule_insufficient_losses():
    """Test confidence calculation with insufficient consecutive losses"""
    rule = Top5ConsecutiveLossesRule()
    team_analysis = create_mock_team_analysis(
        consecutive_losses=1, rank=3
    )  # Less than 2

    confidence = rule.calculate_confidence(team_analysis)
    assert confidence == 0.0


def test_top5_consecutive_losses_rule_valid():
    """Test confidence calculation for valid top 5 team with losses"""
    rule = Top5ConsecutiveLossesRule()
    team_analysis = create_mock_team_analysis(
        consecutive_losses=2, rank=3, consecutive_no_goals=0
    )

    confidence = rule.calculate_confidence(team_analysis)
    assert confidence == 0.7  # Base + 0.2 for top 5


def test_betting_opportunity_creation():
    """Test creating Bet with valid data"""
    opportunity = Bet(
        match_id=123,
        home_team='Team A',
        away_team='Team B',
        league='Premier League',
        country='England',
        rule_name='Test Rule',
        rule_type='test_rule',
        bet_type=BetType.DRAW_OR_WIN,
        confidence=0.75,
        team_analyzed='Team A',
        details={'key': 'value'},
    )

    assert opportunity.match_id == 123
    assert opportunity.home_team == 'Team A'
    assert opportunity.away_team == 'Team B'
    assert opportunity.league == 'Premier League'
    assert opportunity.country == 'England'
    assert opportunity.rule_name == 'Test Rule'
    assert opportunity.rule_type == 'test_rule'
    assert opportunity.bet_type == BetType.DRAW_OR_WIN
    assert opportunity.confidence == 0.75
    assert opportunity.team_analyzed == 'Team A'
    assert opportunity.details == {'key': 'value'}


def test_betting_opportunity_defaults():
    """Test Bet with default values"""
    opportunity = Bet(
        home_team='Team A',
        away_team='Team B',
        league='Premier League',
        country='England',
        rule_name='Test Rule',
        rule_type='test_rule',
        bet_type=BetType.WIN,
        confidence=0.5,
        team_analyzed='Team A',
    )

    assert opportunity.match_id is None
    assert opportunity.rule_type == 'test_rule'
    assert opportunity.details == {}


def test_betting_opportunity_validation_negative_confidence():
    """Test Bet validation with negative confidence"""
    with pytest.raises(ValidationError):
        Bet(
            home_team='Team A',
            away_team='Team B',
            league='Premier League',
            country='England',
            rule_name='Test Rule',
            rule_type='test_rule',
            bet_type=BetType.WIN,
            confidence=-0.1,  # Should be >= 0
            team_analyzed='Team A',
        )


def test_betting_opportunity_validation_high_confidence():
    """Test Bet validation with confidence > 1"""
    with pytest.raises(ValidationError):
        Bet(
            home_team='Team A',
            away_team='Team B',
            league='Premier League',
            country='England',
            rule_name='Test Rule',
            rule_type='test_rule',
            bet_type=BetType.WIN,
            confidence=1.1,  # Should be <= 1
            team_analyzed='Team A',
        )


def test_bet_outcome_values():
    """Test that BetOutcome enum has correct values"""
    assert BetOutcome.WIN.value == 'win'
    assert BetOutcome.LOSE.value == 'lose'


def test_match_result_creation():
    """Test MatchResult DTO creation and properties"""
    match_result = MatchResult(
        home_score=2,
        away_score=1,
        home_team='Home Team',
        away_team='Away Team',
        team_analyzed='Home Team',
    )

    assert match_result.home_score == 2
    assert match_result.away_score == 1
    assert match_result.home_team == 'Home Team'
    assert match_result.away_team == 'Away Team'
    assert match_result.team_analyzed == 'Home Team'
    assert match_result.result_type == 'home_win'


def test_match_result_result_type():
    """Test MatchResult result_type property"""
    # Home win
    match_result = MatchResult(
        home_score=2,
        away_score=1,
        home_team='Home',
        away_team='Away',
        team_analyzed='Home',
    )
    assert match_result.result_type == 'home_win'

    # Away win
    match_result = MatchResult(
        home_score=1,
        away_score=2,
        home_team='Home',
        away_team='Away',
        team_analyzed='Away',
    )
    assert match_result.result_type == 'away_win'

    # Draw
    match_result = MatchResult(
        home_score=1,
        away_score=1,
        home_team='Home',
        away_team='Away',
        team_analyzed='Home',
    )
    assert match_result.result_type == 'draw'

    # Incomplete (None scores)
    match_result = MatchResult(
        home_score=None,
        away_score=1,
        home_team='Home',
        away_team='Away',
        team_analyzed='Home',
    )
    assert match_result.result_type == 'incomplete'

    match_result = MatchResult(
        home_score=1,
        away_score=None,
        home_team='Home',
        away_team='Away',
        team_analyzed='Home',
    )
    assert match_result.result_type == 'incomplete'


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


def test_rule_type_values():
    """Test that rule types are correctly set"""
    consecutive_losses_rule = ConsecutiveLossesRule()
    assert consecutive_losses_rule.rule_type == 'consecutive_losses'

    consecutive_draws_rule = ConsecutiveDrawsRule()
    assert consecutive_draws_rule.rule_type == 'consecutive_draws'

    top5_rule = Top5ConsecutiveLossesRule()
    assert top5_rule.rule_type == 'top5_consecutive_losses'


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


def test_top5_consecutive_losses_rule_determine_outcome():
    """Test Top5ConsecutiveLossesRule determine_outcome method"""
    rule = Top5ConsecutiveLossesRule()

    # Home team (top-5) with consecutive losses - should win if home wins or draws
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

    # Away team (top-5) with consecutive losses - should win if away wins or draws
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
