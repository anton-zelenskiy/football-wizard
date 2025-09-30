#!/usr/bin/env python3
"""
Unit tests for TeamAnalysis and TeamAnalysisService classes
"""

from unittest.mock import Mock

import pytest

from app.bet_rules.team_analysis import TeamAnalysis, TeamAnalysisService
from app.db.models import League, Match, Team


@pytest.fixture
def team_analysis_service():
    """Create a TeamAnalysisService instance for testing"""
    return TeamAnalysisService(top_teams_count=8, min_consecutive_losses=3)


@pytest.fixture
def mock_league():
    """Create a mock league for testing"""
    league = Mock(spec=League)
    league.name = "Test League"
    league.country = "Test Country"
    return league


@pytest.fixture
def mock_teams():
    """Create mock teams for testing"""
    home_team = Mock(spec=Team)
    home_team.name = "Home Team"
    home_team.rank = 5
    home_team.league = Mock(spec=League)
    home_team.league.name = "Test League"
    home_team.league.country = "Test Country"

    away_team = Mock(spec=Team)
    away_team.name = "Away Team"
    away_team.rank = 15
    away_team.league = Mock(spec=League)
    away_team.league.name = "Test League"
    away_team.league.country = "Test Country"

    return home_team, away_team


def create_team_analysis_from_dict(team, team_type, analysis_dict):
    """Helper function to create TeamAnalysis from dictionary for testing"""
    # Calculate wins, draws, losses from win_rate if not provided
    total_matches = analysis_dict.get(
        "total_matches", 100
    )  # Use 100 for better precision
    win_rate = analysis_dict.get("win_rate", 0.0)
    draw_rate = analysis_dict.get("draw_rate", 0.0)

    wins = int(total_matches * win_rate)
    draws = int(total_matches * draw_rate)
    losses = total_matches - wins - draws

    return TeamAnalysis(
        team=team,
        team_type=team_type,
        rank=analysis_dict.get("rank"),
        consecutive_wins=analysis_dict.get("consecutive_wins", 0),
        consecutive_losses=analysis_dict.get("consecutive_losses", 0),
        consecutive_draws=analysis_dict.get("consecutive_draws", 0),
        consecutive_no_goals=analysis_dict.get("consecutive_no_goals", 0),
        consecutive_goals=analysis_dict.get("consecutive_goals", 0),
        recent_matches=analysis_dict.get("recent_matches", []),
        total_matches=total_matches,
        wins=wins,
        draws=draws,
        losses=losses,
        is_top_team=analysis_dict.get("is_top_team", False),
        is_top5_team=analysis_dict.get("is_top5_team", False),
    )


def test_team_analysis_service_init(team_analysis_service):
    """Test TeamAnalysisService initialization"""
    assert team_analysis_service.top_teams_count == 8
    assert team_analysis_service.min_consecutive_losses == 3


def test_analyze_team_performance(team_analysis_service, mock_teams):
    """Test team performance analysis"""
    home_team, _ = mock_teams

    # Mock recent matches with varied outcomes
    mock_matches = []
    for i in range(10):
        match = Mock(spec=Match)
        match.home_team = home_team
        match.away_team = Mock(spec=Team)

        # Create a pattern: first 3 wins, then 2 losses, then 2 draws, then 3 wins
        if i < 3:
            match.home_score = 2
            match.away_score = 0
        elif i < 5:
            match.home_score = 0
            match.away_score = 1
        elif i < 7:
            match.home_score = 1
            match.away_score = 1
        else:
            match.home_score = 2
            match.away_score = 1

        mock_matches.append(match)

    # Use the team analysis service directly
    analysis = team_analysis_service.analyze_team_performance(
        home_team, "home", mock_matches
    )

    # Test basic fields
    assert hasattr(analysis, "consecutive_wins")
    assert hasattr(analysis, "consecutive_losses")
    assert hasattr(analysis, "consecutive_draws")
    assert hasattr(analysis, "consecutive_no_goals")
    assert hasattr(analysis, "consecutive_goals")
    assert hasattr(analysis, "is_top_team")
    assert hasattr(analysis, "is_top5_team")
    assert hasattr(analysis, "total_matches")
    assert hasattr(analysis, "wins")
    assert hasattr(analysis, "draws")
    assert hasattr(analysis, "losses")
    assert hasattr(analysis, "win_rate")
    assert hasattr(analysis, "draw_rate")
    assert hasattr(analysis, "loss_rate")
    assert analysis.team == home_team

    # Test calculated values
    assert analysis.total_matches == 10
    assert analysis.wins == 6  # 3 + 3
    assert analysis.draws == 2
    assert analysis.losses == 2
    assert analysis.win_rate == 0.6
    assert analysis.draw_rate == 0.2
    assert analysis.loss_rate == 0.2


def test_calculate_consecutive_streak(team_analysis_service, mock_teams):
    """Test consecutive streak calculation"""
    home_team, _ = mock_teams

    # Test 1: Simple consecutive wins pattern
    # Most recent first: [win, win, win, loss, loss]
    win_pattern = [
        (2, 0),
        (3, 1),
        (1, 0),  # 3 wins (most recent first)
        (0, 1),
        (0, 2),  # 2 losses
    ]

    win_matches = []
    for home_score, away_score in win_pattern:
        match = Mock(spec=Match)
        match.home_team = home_team
        match.away_team = Mock(spec=Team)
        match.home_score = home_score
        match.away_score = away_score
        win_matches.append(match)

    # Consecutive wins should be 3 from the beginning (most recent)
    consecutive_wins = team_analysis_service._calculate_consecutive_streak(
        win_matches, home_team, "win"
    )
    assert consecutive_wins == 3

    # Test 2: Consecutive no-goals pattern
    # Most recent first: [no-goals, no-goals, goals, goals]
    no_goals_pattern = [
        (0, 1),
        (0, 2),  # 2 no-goals (most recent first)
        (1, 0),
        (2, 1),  # 2 with goals
    ]

    no_goals_matches = []
    for home_score, away_score in no_goals_pattern:
        match = Mock(spec=Match)
        match.home_team = home_team
        match.away_team = Mock(spec=Team)
        match.home_score = home_score
        match.away_score = away_score
        no_goals_matches.append(match)

    # Consecutive no-goals should be 2 from the beginning (most recent)
    consecutive_no_goals = team_analysis_service._calculate_consecutive_streak(
        no_goals_matches, home_team, "no_goals"
    )
    assert consecutive_no_goals == 2

    # Test 3: Mixed pattern
    # Most recent first: [no-goals, no-goals, goals, win, loss]
    mixed_pattern = [
        (0, 1),
        (0, 2),  # 2 no-goals (most recent first)
        (1, 0),  # 1 with goals
        (2, 0),
        (0, 1),  # 1 win, 1 loss
    ]

    mixed_matches = []
    for home_score, away_score in mixed_pattern:
        match = Mock(spec=Match)
        match.home_team = home_team
        match.away_team = Mock(spec=Team)
        match.home_score = home_score
        match.away_score = away_score
        mixed_matches.append(match)

    # Consecutive draws should be 0 since most recent match is not a draw
    consecutive_draws = team_analysis_service._calculate_consecutive_streak(
        mixed_matches, home_team, "draw"
    )
    assert consecutive_draws == 0

    # Consecutive no-goals should be 2 from the beginning (most recent)
    # Pattern: [no-goals(0,1), no-goals(0,2), goals(1,0), win(2,0), loss(0,1)]
    # So from the beginning: no-goals, no-goals = 2 no-goals
    consecutive_no_goals = team_analysis_service._calculate_consecutive_streak(
        mixed_matches, home_team, "no_goals"
    )
    assert consecutive_no_goals == 2

    # Consecutive wins should be 0 since most recent match is not a win
    consecutive_wins = team_analysis_service._calculate_consecutive_streak(
        mixed_matches, home_team, "win"
    )
    assert consecutive_wins == 0

    # Consecutive losses should be 2 since most recent matches are losses
    consecutive_losses = team_analysis_service._calculate_consecutive_streak(
        mixed_matches, home_team, "loss"
    )
    assert consecutive_losses == 2


def test_analyze_team_performance_with_no_matches(team_analysis_service, mock_teams):
    """Test team performance analysis when no recent matches exist"""
    home_team, _ = mock_teams

    # Use the team analysis service directly with empty matches
    analysis = team_analysis_service.analyze_team_performance(home_team, "home", [])

    # Should return default values when no matches exist
    assert analysis.consecutive_wins == 0
    assert analysis.consecutive_losses == 0
    assert analysis.consecutive_draws == 0
    assert analysis.consecutive_no_goals == 0
    assert analysis.consecutive_goals == 0
    assert analysis.total_matches == 0
    assert analysis.wins == 0
    assert analysis.draws == 0
    assert analysis.losses == 0
    assert analysis.win_rate == 0
    assert analysis.draw_rate == 0
    assert analysis.loss_rate == 0


def test_analyze_team_performance_with_single_match(team_analysis_service, mock_teams):
    """Test team performance analysis with only one recent match"""
    home_team, _ = mock_teams

    # Single match - home team wins
    match = Mock(spec=Match)
    match.home_team = home_team
    match.away_team = Mock(spec=Team)
    match.home_score = 2
    match.away_score = 0

    # Use the team analysis service directly
    analysis = team_analysis_service.analyze_team_performance(
        home_team, "home", [match]
    )

    assert analysis.total_matches == 1
    assert analysis.wins == 1
    assert analysis.draws == 0
    assert analysis.losses == 0
    assert analysis.win_rate == 1.0
    assert analysis.draw_rate == 0.0
    assert analysis.loss_rate == 0.0
    assert analysis.consecutive_wins == 1
    assert analysis.consecutive_losses == 0
    assert analysis.consecutive_draws == 0
    assert analysis.consecutive_no_goals == 0
    assert analysis.consecutive_goals == 1


def test_team_won_lost_drew(team_analysis_service, mock_teams):
    """Test team result checking methods"""
    home_team, away_team = mock_teams

    # Test team won
    match = Mock(spec=Match)
    match.home_team = home_team
    match.away_team = away_team
    match.home_score = 2
    match.away_score = 1

    assert team_analysis_service._team_won(match, home_team) is True
    assert team_analysis_service._team_won(match, away_team) is False
    assert team_analysis_service._team_lost(match, home_team) is False
    assert team_analysis_service._team_lost(match, away_team) is True
    assert team_analysis_service._team_drew(match, home_team) is False

    # Test draw
    match.home_score = 1
    match.away_score = 1
    assert team_analysis_service._team_drew(match, home_team) is True


def test_team_no_goals(team_analysis_service, mock_teams):
    """Test team no goals checking"""
    home_team, away_team = mock_teams

    # Test home team scored no goals
    match = Mock(spec=Match)
    match.home_team = home_team
    match.away_team = away_team
    match.home_score = 0
    match.away_score = 2

    # Ensure scores are integers, not None
    assert match.home_score is not None
    assert match.away_score is not None

    # The home team scored 0 goals, so _team_no_goals should return True
    assert team_analysis_service._team_no_goals(match, home_team) is True
    assert team_analysis_service._team_no_goals(match, away_team) is False

    # Test away team scored no goals
    match.home_score = 2
    match.away_score = 0

    assert team_analysis_service._team_no_goals(match, home_team) is False
    assert team_analysis_service._team_no_goals(match, away_team) is True

    # Test both teams scored goals
    match.home_score = 1
    match.away_score = 1

    assert team_analysis_service._team_no_goals(match, home_team) is False
    assert team_analysis_service._team_no_goals(match, away_team) is False


def test_team_result_methods_with_none_scores(team_analysis_service, mock_teams):
    """Test team result methods with None scores"""
    home_team, away_team = mock_teams

    match = Mock(spec=Match)
    match.home_team = home_team
    match.away_team = away_team
    match.home_score = None
    match.away_score = None

    # All methods should return False when scores are None
    assert team_analysis_service._team_won(match, home_team) is False
    assert team_analysis_service._team_lost(match, home_team) is False
    assert team_analysis_service._team_drew(match, home_team) is False
    assert team_analysis_service._team_no_goals(match, home_team) is False


def test_team_result_methods_with_partial_none_scores(
    team_analysis_service, mock_teams
):
    """Test team result methods with partial None scores"""
    home_team, away_team = mock_teams

    match = Mock(spec=Match)
    match.home_team = home_team
    match.away_team = away_team
    match.home_score = 2
    match.away_score = None

    # All methods should return False when one score is None
    assert team_analysis_service._team_won(match, home_team) is False
    assert team_analysis_service._team_lost(match, home_team) is False
    assert team_analysis_service._team_drew(match, home_team) is False
    assert team_analysis_service._team_no_goals(match, home_team) is False


@pytest.mark.parametrize(
    "rank,expected_is_top",
    [
        (1, True),  # Rank 1 should be top team
        (3, True),  # Rank 3 (Ajax) should be top team
        (8, True),  # Rank 8 should be top team (boundary)
        (9, False),  # Rank 9 (FC Volendam) should NOT be top team
        (10, False),  # Rank 10 should NOT be top team
        (15, False),  # Rank 15 should NOT be top team
    ],
)
def test_top_team_classification(team_analysis_service, rank, expected_is_top):
    """Test that team rank classification works correctly with top_teams_count=8"""
    is_top_team = rank <= team_analysis_service.top_teams_count
    assert (
        is_top_team == expected_is_top
    ), f'Rank {rank} should {"be" if expected_is_top else "NOT be"} a top team'


def test_team_analysis_creation(mock_teams):
    """Test TeamAnalysis model creation"""
    home_team, _ = mock_teams

    analysis = TeamAnalysis(
        team=home_team,
        team_type="home",
        rank=5,
        consecutive_wins=3,
        consecutive_losses=1,
        consecutive_draws=2,
        consecutive_no_goals=0,
        consecutive_goals=3,
        recent_matches=[],
        total_matches=10,
        wins=6,
        draws=2,
        losses=2,
    )

    assert analysis.team == home_team
    assert analysis.team_type == "home"
    assert analysis.rank == 5
    assert analysis.consecutive_wins == 3
    assert analysis.consecutive_losses == 1
    assert analysis.consecutive_draws == 2
    assert analysis.consecutive_no_goals == 0
    assert analysis.consecutive_goals == 3
    assert analysis.total_matches == 10
    assert analysis.wins == 6
    assert analysis.draws == 2
    assert analysis.losses == 2
    assert analysis.is_top_team is True
    assert analysis.is_top5_team is True


def test_computed_fields(mock_teams):
    """Test computed fields in TeamAnalysis"""
    home_team, _ = mock_teams

    analysis = TeamAnalysis(
        team=home_team,
        team_type="home",
        rank=5,
        consecutive_wins=0,
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
        consecutive_goals=0,
        recent_matches=[],
        total_matches=10,
        wins=6,
        draws=2,
        losses=2,
    )

    # Test computed rates
    assert analysis.win_rate == 0.6  # 6/10
    assert analysis.draw_rate == 0.2  # 2/10
    assert analysis.loss_rate == 0.2  # 2/10


def test_computed_fields_with_zero_matches(mock_teams):
    """Test computed fields when no matches exist"""
    home_team, _ = mock_teams

    analysis = TeamAnalysis(
        team=home_team,
        team_type="home",
        rank=5,
        consecutive_wins=0,
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
        consecutive_goals=0,
        recent_matches=[],
        total_matches=0,
        wins=0,
        draws=0,
        losses=0,
    )

    # Test computed rates with zero matches
    assert analysis.win_rate == 0.0
    assert analysis.draw_rate == 0.0
    assert analysis.loss_rate == 0.0


def test_goals_calculations(mock_teams):
    """Test goals_scored and goals_conceded computed fields"""
    home_team, away_team = mock_teams

    # Create mock matches
    match1 = Mock(spec=Match)
    match1.home_team = home_team
    match1.away_team = away_team
    match1.home_score = 2
    match1.away_score = 1

    match2 = Mock(spec=Match)
    match2.home_team = home_team
    match2.away_team = away_team
    match2.home_score = 1
    match2.away_score = 0

    analysis = TeamAnalysis(
        team=home_team,
        team_type="home",
        rank=5,
        consecutive_wins=0,
        consecutive_losses=0,
        consecutive_draws=0,
        consecutive_no_goals=0,
        consecutive_goals=0,
        recent_matches=[match1, match2],
        total_matches=2,
        wins=2,
        draws=0,
        losses=0,
    )

    # Test goals calculations
    assert analysis.goals_scored == 3  # 2 + 1
    assert analysis.goals_conceded == 1  # 1 + 0


if __name__ == "__main__":
    pytest.main([__file__])
