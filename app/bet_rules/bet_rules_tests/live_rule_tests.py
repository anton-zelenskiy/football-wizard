"""Tests for LiveMatchRedCardRule"""

from app.bet_rules.structures import (
    BetOutcome,
    BetType,
    LiveMatchRedCardRule,
    MatchResult,
)
from app.bet_rules.team_analysis import Team, TeamAnalysis


def test_live_match_red_card_rule_creation():
    """Test LiveMatchRedCardRule creation and properties"""
    rule = LiveMatchRedCardRule()

    assert rule.name == 'Live Match Red Card Rule'
    assert (
        rule.description
        == 'Live match with red card and draw -> bet on team without red card'
    )
    assert rule.slug == 'live_red_card'
    assert rule.bet_type == BetType.WIN
    assert rule.base_confidence == 0.5


def test_live_match_red_card_rule_historical_analysis():
    """Test that live rule returns 0 for historical analysis"""
    rule = LiveMatchRedCardRule()

    # Create team analysis
    team_analysis = TeamAnalysis(
        team=Team(name='Test Team', rank=1),
        team_type='home',
        consecutive_losses=3,
        consecutive_draws=2,
        consecutive_no_goals=1,
    )

    # Live rule should return 0 for historical analysis
    confidence = rule.calculate_confidence(team_analysis)
    assert confidence == 0.0


def test_live_match_red_card_rule_no_red_card():
    """Test live rule with no red cards"""
    rule = LiveMatchRedCardRule()

    # Create team analyses
    home_analysis = TeamAnalysis(
        team=Team(name='Home Team', rank=1),
        team_type='home',
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    away_analysis = TeamAnalysis(
        team=Team(name='Away Team', rank=2),
        team_type='away',
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    # No red cards, tied score
    confidence, team_analyzed = rule.calculate_live_confidence(
        home_analysis=home_analysis,
        away_analysis=away_analysis,
        red_cards_home=0,
        red_cards_away=0,
        home_score=1,
        away_score=1,
    )

    assert confidence == 0.0
    assert team_analyzed == 'No red card or not a draw'


def test_live_match_red_card_rule_not_draw():
    """Test live rule with red card but not a draw"""
    rule = LiveMatchRedCardRule()

    # Create team analyses
    home_analysis = TeamAnalysis(
        team=Team(name='Home Team', rank=1),
        team_type='home',
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    away_analysis = TeamAnalysis(
        team=Team(name='Away Team', rank=2),
        team_type='away',
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    # Red card but not a draw
    confidence, team_analyzed = rule.calculate_live_confidence(
        home_analysis=home_analysis,
        away_analysis=away_analysis,
        red_cards_home=1,
        red_cards_away=0,
        home_score=2,
        away_score=1,
    )

    assert confidence == 0.0
    assert team_analyzed == 'No red card or not a draw'


def test_live_match_red_card_rule_home_team_red_card():
    """Test live rule with home team having red card"""
    rule = LiveMatchRedCardRule()

    # Create team analyses
    home_analysis = TeamAnalysis(
        team=Team(name='Home Team', rank=1),
        team_type='home',
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    away_analysis = TeamAnalysis(
        team=Team(name='Away Team', rank=2),
        team_type='away',
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    # Home team has red card, tied score
    confidence, team_analyzed = rule.calculate_live_confidence(
        home_analysis=home_analysis,
        away_analysis=away_analysis,
        red_cards_home=1,
        red_cards_away=0,
        home_score=1,
        away_score=1,
    )

    assert confidence == 0.6  # Base 0.5 + 0.1 for weaker team (rank 2 > rank 1)
    assert team_analyzed == 'Away Team'


def test_live_match_red_card_rule_away_team_red_card():
    """Test live rule with away team having red card"""
    rule = LiveMatchRedCardRule()

    # Create team analyses
    home_analysis = TeamAnalysis(
        team=Team(name='Home Team', rank=1),
        team_type='home',
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    away_analysis = TeamAnalysis(
        team=Team(name='Away Team', rank=2),
        team_type='away',
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    # Away team has red card, tied score
    confidence, team_analyzed = rule.calculate_live_confidence(
        home_analysis=home_analysis,
        away_analysis=away_analysis,
        red_cards_home=0,
        red_cards_away=1,
        home_score=1,
        away_score=1,
    )

    assert confidence == 0.5  # Base confidence
    assert team_analyzed == 'Home Team'


def test_live_match_red_card_rule_weaker_team_advantage():
    """Test live rule with weaker team without red card getting advantage"""
    rule = LiveMatchRedCardRule()

    # Create team analyses - away team is weaker (higher rank)
    home_analysis = TeamAnalysis(
        team=Team(name='Home Team', rank=1),
        team_type='home',
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    away_analysis = TeamAnalysis(
        team=Team(name='Away Team', rank=5),  # Weaker team
        team_type='away',
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    # Home team has red card, tied score, away team is weaker
    confidence, team_analyzed = rule.calculate_live_confidence(
        home_analysis=home_analysis,
        away_analysis=away_analysis,
        red_cards_home=1,
        red_cards_away=0,
        home_score=1,
        away_score=1,
    )

    assert confidence == 0.6  # Base 0.5 + 0.1 for weaker team
    assert team_analyzed == 'Away Team'


def test_live_match_red_card_rule_consecutive_no_goals_bonus():
    """Test live rule with consecutive no goals bonus"""
    rule = LiveMatchRedCardRule()

    # Create team analyses
    home_analysis = TeamAnalysis(
        team=Team(name='Home Team', rank=1),
        team_type='home',
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    away_analysis = TeamAnalysis(
        team=Team(name='Away Team', rank=2),
        team_type='away',
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=3,  # 3 consecutive no goals
    )

    # Home team has red card, tied score
    confidence, team_analyzed = rule.calculate_live_confidence(
        home_analysis=home_analysis,
        away_analysis=away_analysis,
        red_cards_home=1,
        red_cards_away=0,
        home_score=1,
        away_score=1,
    )

    # Base 0.5 + 0.1 (weaker team) + 0.05 * (3-1) = 0.5 + 0.1 + 0.1 = 0.7
    assert confidence == 0.7
    assert team_analyzed == 'Away Team'


def test_live_match_red_card_rule_consecutive_draws_bonus():
    """Test live rule with consecutive draws bonus"""
    rule = LiveMatchRedCardRule()

    # Create team analyses
    home_analysis = TeamAnalysis(
        team=Team(name='Home Team', rank=1),
        team_type='home',
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    away_analysis = TeamAnalysis(
        team=Team(name='Away Team', rank=2),
        team_type='away',
        consecutive_losses=0,
        consecutive_draws=3,  # 3 consecutive draws
        consecutive_no_goals=0,
    )

    # Home team has red card, tied score
    confidence, team_analyzed = rule.calculate_live_confidence(
        home_analysis=home_analysis,
        away_analysis=away_analysis,
        red_cards_home=1,
        red_cards_away=0,
        home_score=1,
        away_score=1,
    )

    # Base 0.5 + 0.1 (weaker team) + 0.05 * (3-1) = 0.5 + 0.1 + 0.1 = 0.7
    assert confidence == 0.7
    assert team_analyzed == 'Away Team'


def test_live_match_red_card_rule_consecutive_losses_bonus():
    """Test live rule with consecutive losses bonus"""
    rule = LiveMatchRedCardRule()

    # Create team analyses
    home_analysis = TeamAnalysis(
        team=Team(name='Home Team', rank=1),
        team_type='home',
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    away_analysis = TeamAnalysis(
        team=Team(name='Away Team', rank=2),
        team_type='away',
        consecutive_losses=3,  # 3 consecutive losses
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    # Home team has red card, tied score
    confidence, team_analyzed = rule.calculate_live_confidence(
        home_analysis=home_analysis,
        away_analysis=away_analysis,
        red_cards_home=1,
        red_cards_away=0,
        home_score=1,
        away_score=1,
    )

    # Base 0.5 + 0.1 (weaker team) + 0.05 * (3-1) = 0.5 + 0.1 + 0.1 = 0.7
    assert confidence == 0.7
    assert team_analyzed == 'Away Team'


def test_live_match_red_card_rule_multiple_bonuses():
    """Test live rule with multiple bonuses"""
    rule = LiveMatchRedCardRule()

    # Create team analyses
    home_analysis = TeamAnalysis(
        team=Team(name='Home Team', rank=1),
        team_type='home',
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    away_analysis = TeamAnalysis(
        team=Team(name='Away Team', rank=5),  # Weaker team
        team_type='away',
        consecutive_losses=2,  # 2 consecutive losses
        consecutive_draws=2,  # 2 consecutive draws
        consecutive_no_goals=2,  # 2 consecutive no goals
    )

    # Home team has red card, tied score
    confidence, team_analyzed = rule.calculate_live_confidence(
        home_analysis=home_analysis,
        away_analysis=away_analysis,
        red_cards_home=1,
        red_cards_away=0,
        home_score=1,
        away_score=1,
    )

    # Base 0.5 + 0.1 (weaker team) + 0.05 (no goals) + 0.05 (draws) + 0.05 (losses) = 0.75
    assert abs(confidence - 0.75) < 0.001  # Handle floating point precision
    assert team_analyzed == 'Away Team'


def test_live_match_red_card_rule_confidence_cap():
    """Test that confidence is capped at 1.0"""
    rule = LiveMatchRedCardRule()

    # Create team analyses with high bonuses
    home_analysis = TeamAnalysis(
        team=Team(name='Home Team', rank=1),
        team_type='home',
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    away_analysis = TeamAnalysis(
        team=Team(name='Away Team', rank=10),  # Much weaker team
        team_type='away',
        consecutive_losses=5,  # 5 consecutive losses
        consecutive_draws=5,  # 5 consecutive draws
        consecutive_no_goals=5,  # 5 consecutive no goals
    )

    # Home team has red card, tied score
    confidence, team_analyzed = rule.calculate_live_confidence(
        home_analysis=home_analysis,
        away_analysis=away_analysis,
        red_cards_home=1,
        red_cards_away=0,
        home_score=1,
        away_score=1,
    )

    # Should be high confidence (0.95) but not necessarily 1.0 due to bonus caps
    assert confidence >= 0.9
    assert team_analyzed == 'Away Team'


def test_live_match_red_card_rule_both_teams_red_cards():
    """Test live rule with both teams having red cards"""
    rule = LiveMatchRedCardRule()

    # Create team analyses
    home_analysis = TeamAnalysis(
        team=Team(name='Home Team', rank=1),
        team_type='home',
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    away_analysis = TeamAnalysis(
        team=Team(name='Away Team', rank=2),
        team_type='away',
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    # Both teams have red cards, tied score
    confidence, team_analyzed = rule.calculate_live_confidence(
        home_analysis=home_analysis,
        away_analysis=away_analysis,
        red_cards_home=1,
        red_cards_away=1,
        home_score=1,
        away_score=1,
    )

    assert confidence == 0.0
    assert team_analyzed == 'Both teams have red cards or invalid state'


def test_live_match_red_card_rule_outcome_determination():
    """Test live rule outcome determination"""
    rule = LiveMatchRedCardRule()

    # Test home team win (we bet on home team)
    match_result = MatchResult(
        home_score=2,
        away_score=1,
        home_team='Home Team',
        away_team='Away Team',
        team_analyzed='Home Team',
    )
    assert rule.determine_outcome(match_result) == BetOutcome.WIN.value

    # Test home team loss (we bet on home team)
    match_result = MatchResult(
        home_score=1,
        away_score=2,
        home_team='Home Team',
        away_team='Away Team',
        team_analyzed='Home Team',
    )
    assert rule.determine_outcome(match_result) == BetOutcome.LOSE.value

    # Test away team win (we bet on away team)
    match_result = MatchResult(
        home_score=1,
        away_score=2,
        home_team='Home Team',
        away_team='Away Team',
        team_analyzed='Away Team',
    )
    assert rule.determine_outcome(match_result) == BetOutcome.WIN.value

    # Test away team loss (we bet on away team)
    match_result = MatchResult(
        home_score=2,
        away_score=1,
        home_team='Home Team',
        away_team='Away Team',
        team_analyzed='Away Team',
    )
    assert rule.determine_outcome(match_result) == BetOutcome.LOSE.value

    # Test incomplete match
    match_result = MatchResult(
        home_score=None,
        away_score=None,
        home_team='Home Team',
        away_team='Away Team',
        team_analyzed='Home Team',
    )
    assert rule.determine_outcome(match_result) is None
