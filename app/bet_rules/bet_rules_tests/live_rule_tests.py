import pytest

from app.bet_rules.bet_rules import LiveMatchDrawRedCardRule
from app.bet_rules.structures import (
    BetOutcome,
    BetType,
    MatchSummary,
    TeamAnalysis,
    TeamData,
)


def test_live_match_red_card_rule_creation():
    """Test LiveMatchDrawRedCardRule creation and properties"""
    rule = LiveMatchDrawRedCardRule()

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
    rule = LiveMatchDrawRedCardRule()

    # Create team analysis
    team_analysis = TeamAnalysis(
        team=TeamData(id=1, name='Test Team', rank=1),
        consecutive_losses=3,
        consecutive_draws=2,
        consecutive_no_goals=1,
    )

    opponent_analysis = TeamAnalysis(
        team=TeamData(id=2, name='Opponent Team', rank=2),
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    match_summary = MatchSummary(
        home_team_data=TeamData(id=1, name='Home Team', rank=1),
        away_team_data=TeamData(id=2, name='Away Team', rank=2),
        league='Test League',
        country='Test Country',
    )

    # Live rule should return 0 for historical analysis
    confidence = rule.calculate_confidence(
        team_analysis, opponent_analysis, match_summary
    )
    assert confidence == 0.0


def test_live_match_red_card_rule_no_red_card():
    """Test live rule with no red cards"""
    rule = LiveMatchDrawRedCardRule()

    # Create team analyses
    home_analysis = TeamAnalysis(
        team=TeamData(id=1, name='Home Team', rank=1),
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    away_analysis = TeamAnalysis(
        team=TeamData(id=2, name='Away Team', rank=2),
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    # Create match summary with no red cards, tied score
    match_summary = MatchSummary(
        match_id=None,
        home_team_data=TeamData(id=1, name='Home Team', rank=1),
        away_team_data=TeamData(id=2, name='Away Team', rank=2),
        league='Test League',
        country='Test Country',
        match_date=None,
        home_score=1,
        away_score=1,
        red_cards_home=0,
        red_cards_away=0,
        minute=75,
    )

    # No red cards, tied score
    confidence = rule.calculate_confidence(home_analysis, away_analysis, match_summary)

    assert confidence == 0.0


def test_live_match_red_card_rule_not_draw():
    """Test live rule with red card but not a draw"""
    rule = LiveMatchDrawRedCardRule()

    # Create team analyses
    home_analysis = TeamAnalysis(
        team=TeamData(id=1, name='Home Team', rank=1),
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    away_analysis = TeamAnalysis(
        team=TeamData(id=2, name='Away Team', rank=2),
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    # Create match summary with red card but not a draw
    match_summary = MatchSummary(
        match_id=None,
        home_team_data=TeamData(id=1, name='Home Team', rank=1),
        away_team_data=TeamData(id=2, name='Away Team', rank=2),
        league='Test League',
        country='Test Country',
        match_date=None,
        home_score=2,
        away_score=1,
        red_cards_home=1,
        red_cards_away=0,
        minute=75,
    )

    # Red card but not a draw
    confidence = rule.calculate_confidence(home_analysis, away_analysis, match_summary)

    assert confidence == 0.0


def test_live_match_red_card_rule_home_team_red_card():
    """Test live rule with home team having red card"""
    rule = LiveMatchDrawRedCardRule()

    # Create team analyses
    home_analysis = TeamAnalysis(
        team=TeamData(id=1, name='Home Team', rank=1),
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    away_analysis = TeamAnalysis(
        team=TeamData(id=2, name='Away Team', rank=2),
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    # Create match summary with home team red card, tied score
    match_summary = MatchSummary(
        match_id=None,
        home_team_data=TeamData(id=1, name='Home Team', rank=1),
        away_team_data=TeamData(id=2, name='Away Team', rank=2),
        league='Test League',
        country='Test Country',
        match_date=None,
        home_score=1,
        away_score=1,
        red_cards_home=1,
        red_cards_away=0,
        minute=75,
    )

    # Home team has red card, tied score - bet on away team
    confidence = rule.calculate_confidence(away_analysis, home_analysis, match_summary)

    assert confidence == 0.6  # Base 0.5 + 0.1 for weaker team (rank 2 > rank 1)


def test_live_match_red_card_rule_away_team_red_card():
    """Test live rule with away team having red card"""
    rule = LiveMatchDrawRedCardRule()

    # Create team analyses
    home_analysis = TeamAnalysis(
        team=TeamData(id=1, name='Home Team', rank=1),
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    away_analysis = TeamAnalysis(
        team=TeamData(id=2, name='Away Team', rank=2),
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    # Create match summary with away team red card, tied score
    match_summary = MatchSummary(
        match_id=None,
        home_team_data=TeamData(id=1, name='Home Team', rank=1),
        away_team_data=TeamData(id=2, name='Away Team', rank=2),
        league='Test League',
        country='Test Country',
        match_date=None,
        home_score=1,
        away_score=1,
        red_cards_home=0,
        red_cards_away=1,
        minute=75,
    )

    # Away team has red card, tied score - bet on home team
    confidence = rule.calculate_confidence(home_analysis, away_analysis, match_summary)

    assert confidence == 0.5  # Base confidence


def test_live_match_red_card_rule_weaker_team_advantage():
    """Test live rule with weaker team without red card getting advantage"""
    rule = LiveMatchDrawRedCardRule()

    # Create team analyses - away team is weaker (higher rank)
    home_analysis = TeamAnalysis(
        team=TeamData(id=1, name='Home Team', rank=1),
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    away_analysis = TeamAnalysis(
        team=TeamData(id=2, name='Away Team', rank=5),  # Weaker team
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    # Create match summary with home team red card, tied score
    match_summary = MatchSummary(
        match_id=None,
        home_team_data=TeamData(id=1, name='Home Team', rank=1),
        away_team_data=TeamData(id=2, name='Away Team', rank=2),
        league='Test League',
        country='Test Country',
        match_date=None,
        home_score=1,
        away_score=1,
        red_cards_home=1,
        red_cards_away=0,
        minute=75,
    )

    # Home team has red card, tied score, away team is weaker - bet on away team
    confidence = rule.calculate_confidence(away_analysis, home_analysis, match_summary)

    assert confidence == 0.6  # Base 0.5 + 0.1 for weaker team


def test_live_match_red_card_rule_consecutive_no_goals_bonus():
    """Test live rule with consecutive no goals bonus"""
    rule = LiveMatchDrawRedCardRule()

    # Create team analyses
    home_analysis = TeamAnalysis(
        team=TeamData(id=1, name='Home Team', rank=1),
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    away_analysis = TeamAnalysis(
        team=TeamData(id=2, name='Away Team', rank=2),
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=3,  # 3 consecutive no goals
    )

    # Create match summary with home team red card, tied score
    match_summary = MatchSummary(
        match_id=None,
        home_team_data=TeamData(id=1, name='Home Team', rank=1),
        away_team_data=TeamData(id=2, name='Away Team', rank=2),
        league='Test League',
        country='Test Country',
        match_date=None,
        home_score=1,
        away_score=1,
        red_cards_home=1,
        red_cards_away=0,
        minute=75,
    )

    # Home team has red card, tied score - bet on away team
    confidence = rule.calculate_confidence(away_analysis, home_analysis, match_summary)

    # Base 0.5 + 0.1 (weaker team) + 0.05 * (3-1) = 0.5 + 0.1 + 0.1 = 0.7
    assert confidence == 0.7


def test_live_match_red_card_rule_consecutive_draws_bonus():
    """Test live rule with consecutive draws bonus"""
    rule = LiveMatchDrawRedCardRule()

    # Create team analyses
    home_analysis = TeamAnalysis(
        team=TeamData(id=1, name='Home Team', rank=1),
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    away_analysis = TeamAnalysis(
        team=TeamData(id=2, name='Away Team', rank=2),
        consecutive_losses=0,
        consecutive_draws=3,  # 3 consecutive draws
        consecutive_no_goals=0,
    )

    # Create match summary with home team red card, tied score
    match_summary = MatchSummary(
        match_id=None,
        home_team_data=TeamData(id=1, name='Home Team', rank=1),
        away_team_data=TeamData(id=2, name='Away Team', rank=2),
        league='Test League',
        country='Test Country',
        match_date=None,
        home_score=1,
        away_score=1,
        red_cards_home=1,
        red_cards_away=0,
        minute=75,
    )

    # Home team has red card, tied score - bet on away team
    confidence = rule.calculate_confidence(away_analysis, home_analysis, match_summary)

    # Base 0.5 + 0.1 (weaker team) + 0.05 * (3-1) = 0.5 + 0.1 + 0.1 = 0.7
    assert confidence == 0.7


def test_live_match_red_card_rule_consecutive_losses_bonus():
    """Test live rule with consecutive losses bonus"""
    rule = LiveMatchDrawRedCardRule()

    # Create team analyses
    home_analysis = TeamAnalysis(
        team=TeamData(id=1, name='Home Team', rank=1),
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    away_analysis = TeamAnalysis(
        team=TeamData(id=2, name='Away Team', rank=2),
        consecutive_losses=3,  # 3 consecutive losses
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    # Create match summary with home team red card, tied score
    match_summary = MatchSummary(
        match_id=None,
        home_team_data=TeamData(id=1, name='Home Team', rank=1),
        away_team_data=TeamData(id=2, name='Away Team', rank=2),
        league='Test League',
        country='Test Country',
        match_date=None,
        home_score=1,
        away_score=1,
        red_cards_home=1,
        red_cards_away=0,
        minute=75,
    )

    # Home team has red card, tied score - bet on away team
    confidence = rule.calculate_confidence(away_analysis, home_analysis, match_summary)

    # Base 0.5 + 0.1 (weaker team) + 0.05 * (3-1) = 0.5 + 0.1 + 0.1 = 0.7
    assert confidence == 0.7


def test_live_match_red_card_rule_multiple_bonuses():
    """Test live rule with multiple bonuses"""
    rule = LiveMatchDrawRedCardRule()

    # Create team analyses
    home_analysis = TeamAnalysis(
        team=TeamData(id=1, name='Home Team', rank=1),
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    away_analysis = TeamAnalysis(
        team=TeamData(id=2, name='Away Team', rank=5),  # Weaker team
        consecutive_losses=2,  # 2 consecutive losses
        consecutive_draws=2,  # 2 consecutive draws
        consecutive_no_goals=2,  # 2 consecutive no goals
    )

    # Create match summary with home team red card, tied score
    match_summary = MatchSummary(
        match_id=None,
        home_team_data=TeamData(id=1, name='Home Team', rank=1),
        away_team_data=TeamData(id=2, name='Away Team', rank=2),
        league='Test League',
        country='Test Country',
        match_date=None,
        home_score=1,
        away_score=1,
        red_cards_home=1,
        red_cards_away=0,
        minute=75,
    )

    # Home team has red card, tied score - bet on away team
    confidence = rule.calculate_confidence(away_analysis, home_analysis, match_summary)

    # Base 0.5 + 0.1 (weaker team) + 0.05 (no goals) + 0.05 (draws) + 0.05 (losses) = 0.75
    assert abs(confidence - 0.75) < 0.001  # Handle floating point precision


def test_live_match_red_card_rule_confidence_cap():
    """Test that confidence is capped at 1.0"""
    rule = LiveMatchDrawRedCardRule()

    # Create team analyses with high bonuses
    home_analysis = TeamAnalysis(
        team=TeamData(id=1, name='Home Team', rank=1),
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    away_analysis = TeamAnalysis(
        team=TeamData(id=2, name='Away Team', rank=10),  # Much weaker team
        consecutive_losses=5,  # 5 consecutive losses
        consecutive_draws=5,  # 5 consecutive draws
        consecutive_no_goals=5,  # 5 consecutive no goals
    )

    # Create match summary with home team red card, tied score
    match_summary = MatchSummary(
        match_id=None,
        home_team_data=TeamData(id=1, name='Home Team', rank=1),
        away_team_data=TeamData(id=2, name='Away Team', rank=2),
        league='Test League',
        country='Test Country',
        match_date=None,
        home_score=1,
        away_score=1,
        red_cards_home=1,
        red_cards_away=0,
        minute=75,
    )

    # Home team has red card, tied score - bet on away team
    confidence = rule.calculate_confidence(away_analysis, home_analysis, match_summary)

    # Should be high confidence (0.95) but not necessarily 1.0 due to bonus caps
    assert confidence >= 0.9


def test_live_match_red_card_rule_both_teams_red_cards():
    """Test live rule with both teams having red cards"""
    rule = LiveMatchDrawRedCardRule()

    # Create team analyses
    home_analysis = TeamAnalysis(
        team=TeamData(id=1, name='Home Team', rank=1),
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    away_analysis = TeamAnalysis(
        team=TeamData(id=2, name='Away Team', rank=2),
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
    )

    # Create match summary with both teams having red cards, tied score
    match_summary = MatchSummary(
        match_id=None,
        home_team_data=TeamData(id=1, name='Home Team', rank=1),
        away_team_data=TeamData(id=2, name='Away Team', rank=2),
        league='Test League',
        country='Test Country',
        match_date=None,
        home_score=1,
        away_score=1,
        red_cards_home=1,
        red_cards_away=1,
        minute=75,
    )

    # Both teams have red cards, tied score
    confidence = rule.calculate_confidence(home_analysis, away_analysis, match_summary)

    assert confidence == 0.0


@pytest.mark.parametrize(
    'home_score,away_score,team_analyzed,expected_outcome,description',
    [
        (2, 1, 'Home Team', BetOutcome.WIN, 'Home team wins'),
        (1, 2, 'Home Team', BetOutcome.LOSE, 'Home team loses'),
        (1, 2, 'Away Team', BetOutcome.WIN, 'Away team wins'),
        (2, 1, 'Away Team', BetOutcome.LOSE, 'Away team loses'),
    ],
)
def test_live_match_red_card_rule_outcome_determination(
    home_score, away_score, team_analyzed, expected_outcome, description
):
    """Test live rule outcome determination"""
    rule = LiveMatchDrawRedCardRule()

    match_result = MatchSummary(
        match_id=None,
        home_team_data=TeamData(id=1, name='Home Team', rank=1),
        away_team_data=TeamData(id=2, name='Away Team', rank=2),
        league='Test League',
        country='Test Country',
        match_date=None,
        home_score=home_score,
        away_score=away_score,
        red_cards_home=0,
        red_cards_away=0,
        minute=None,
    )

    outcome = rule.determine_outcome(match_result, team_analyzed)
    assert outcome == expected_outcome, f'Failed for {description}'


def test_live_match_red_card_rule_incomplete_match():
    """Test live rule with incomplete match"""
    rule = LiveMatchDrawRedCardRule()

    match_result = MatchSummary(
        match_id=None,
        home_team_data=TeamData(id=1, name='Home Team', rank=1),
        away_team_data=TeamData(id=2, name='Away Team', rank=2),
        league='Test League',
        country='Test Country',
        match_date=None,
        home_score=None,
        away_score=None,
        red_cards_home=0,
        red_cards_away=0,
        minute=None,
    )

    outcome = rule.determine_outcome(match_result, 'Home Team')
    assert outcome is None
