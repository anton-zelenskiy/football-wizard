from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.bet_rules.team_analysis import TeamAnalysis


class BetType(str, Enum):
    """Betting outcome types"""

    WIN = 'win'
    DRAW = 'draw'
    LOSE = 'lose'
    DRAW_OR_WIN = 'draw_or_win'
    WIN_OR_LOSE = 'win_or_lose'
    GOAL = 'goal'


class BetOutcome(str, Enum):
    """Betting result outcomes"""

    WIN = 'win'
    LOSE = 'lose'


class MatchResult(BaseModel):
    """Match result information for outcome determination"""

    home_score: int | None = Field(description='Home team score')
    away_score: int | None = Field(description='Away team score')
    home_team: str = Field(description='Home team name')
    away_team: str = Field(description='Away team name')
    team_analyzed: str = Field(description='Team that was analyzed for the bet')

    @property
    def result_type(self) -> str:
        """Determine the match result type"""
        if self.home_score is None or self.away_score is None:
            return 'incomplete'
        elif self.home_score > self.away_score:
            return 'home_win'
        elif self.away_score > self.home_score:
            return 'away_win'
        else:
            return 'draw'


class BettingRule(BaseModel):
    """Base betting rule model"""

    name: str = Field(description='Rule name')
    description: str = Field(description='Rule description')
    rule_type: str = Field(description='Rule type identifier')
    bet_type: BetType = Field(description='Expected bet type')
    base_confidence: float = Field(default=0.5, ge=0.0, le=1.0, description='Base confidence level')

    def calculate_confidence(self, team_analysis: TeamAnalysis) -> float:
        """Calculate confidence based on team analysis"""
        raise NotImplementedError('Subclasses must implement calculate_confidence')

    def determine_outcome(self, match_result: 'MatchResult') -> str | None:
        """Determine if the bet was won or lost based on match result"""
        raise NotImplementedError('Subclasses must implement determine_outcome')

    @property
    def _base_confidence_calculator(self):
        """Base confidence calculation with common factors"""

        def calculate(team_analysis: TeamAnalysis) -> float:
            confidence = self.base_confidence

            # Add confidence based on team rank
            if team_analysis.is_top5_team:
                confidence += 0.2
            elif team_analysis.is_top_team:
                confidence += 0.1

            # Add confidence for no goals in last 2, 3, 4, or 5 matches
            no_goals_streak = team_analysis.consecutive_no_goals
            for min_streak in [2, 3, 4, 5]:
                if no_goals_streak >= min_streak:
                    confidence += 0.05

            return min(1.0, confidence)

        return calculate


class ConsecutiveLossesRule(BettingRule):
    """Rule: Team has >= 3 consecutive losses -> draw_or_win"""

    def __init__(self, **data: Any) -> None:
        super().__init__(
            name='Consecutive Losses Rule',
            description='Team with >= 3 consecutive losses -> draw_or_win',
            rule_type='consecutive_losses',
            bet_type=BetType.DRAW_OR_WIN,
            base_confidence=0.5,
            **data,
        )

    def calculate_confidence(self, team_analysis: TeamAnalysis) -> float:
        """Calculate confidence for consecutive losses rule"""
        if team_analysis.consecutive_losses < 3:
            return 0.0

        return self._base_confidence_calculator(team_analysis)

    def determine_outcome(self, match_result: 'MatchResult') -> str | None:
        """Determine outcome for consecutive losses rule (draw_or_win)"""
        from .models import BetOutcome

        # Check if match is incomplete
        if match_result.result_type == 'incomplete':
            return None

        if match_result.team_analyzed == match_result.home_team:
            # Home team is the one with consecutive losses
            if match_result.result_type in ['home_win', 'draw']:
                return BetOutcome.WIN.value
            else:
                return BetOutcome.LOSE.value
        elif match_result.team_analyzed == match_result.away_team:
            # Away team is the one with consecutive losses
            if match_result.result_type in ['away_win', 'draw']:
                return BetOutcome.WIN.value
            else:
                return BetOutcome.LOSE.value
        else:
            # Both teams fit the rule - check if either team didn't lose
            if match_result.result_type == 'draw':
                return BetOutcome.WIN.value
            else:
                return BetOutcome.LOSE.value


class ConsecutiveDrawsRule(BettingRule):
    """Rule: Team has >= 3 consecutive draws -> win_or_lose"""

    def __init__(self, **data: Any) -> None:
        super().__init__(
            name='Consecutive Draws Rule',
            description='Team with >= 3 consecutive draws -> win_or_lose',
            rule_type='consecutive_draws',
            bet_type=BetType.WIN_OR_LOSE,
            base_confidence=0.5,
            **data,
        )

    def calculate_confidence(self, team_analysis: TeamAnalysis) -> float:
        """Calculate confidence for consecutive draws rule"""
        if team_analysis.consecutive_draws < 3:
            return 0.0

        return self._base_confidence_calculator(team_analysis)

    def determine_outcome(self, match_result: 'MatchResult') -> str | None:
        """Determine outcome for consecutive draws rule (win_or_lose)"""
        from .models import BetOutcome

        # Check if match is incomplete
        if match_result.result_type == 'incomplete':
            return None

        if match_result.team_analyzed == match_result.home_team:
            # Home team is the one with consecutive draws
            if match_result.result_type == 'home_win':
                return BetOutcome.WIN.value
            else:
                return BetOutcome.LOSE.value
        elif match_result.team_analyzed == match_result.away_team:
            # Away team is the one with consecutive draws
            if match_result.result_type == 'away_win':
                return BetOutcome.WIN.value
            else:
                return BetOutcome.LOSE.value
        else:
            # Both teams fit the rule - check if either team won
            if match_result.result_type in ['home_win', 'away_win']:
                return BetOutcome.WIN.value
            else:
                return BetOutcome.LOSE.value


class Top5ConsecutiveLossesRule(BettingRule):
    """Rule: Team from top-5 and >= 2 consecutive losses -> draw_or_win"""

    def __init__(self, **data: Any) -> None:
        super().__init__(
            name='Top 5 Consecutive Losses Rule',
            description='Top 5 team with >= 2 consecutive losses -> draw_or_win',
            rule_type='top5_consecutive_losses',
            bet_type=BetType.DRAW_OR_WIN,
            base_confidence=0.5,
            **data,
        )

    def calculate_confidence(self, team_analysis: TeamAnalysis) -> float:
        """Calculate confidence for top 5 consecutive losses rule"""
        if not team_analysis.is_top5_team or team_analysis.consecutive_losses < 2:
            return 0.0

        return self._base_confidence_calculator(team_analysis)

    def determine_outcome(self, match_result: 'MatchResult') -> str | None:
        """Determine outcome for top-5 consecutive losses rule (draw_or_win)"""
        from .models import BetOutcome

        # Check if match is incomplete
        if match_result.result_type == 'incomplete':
            return None

        if match_result.team_analyzed == match_result.home_team:
            # Home team is the top-5 team with consecutive losses
            if match_result.result_type in ['home_win', 'draw']:
                return BetOutcome.WIN.value
            else:
                return BetOutcome.LOSE.value
        elif match_result.team_analyzed == match_result.away_team:
            # Away team is the top-5 team with consecutive losses
            if match_result.result_type in ['away_win', 'draw']:
                return BetOutcome.WIN.value
            else:
                return BetOutcome.LOSE.value
        else:
            # Both teams fit the rule - check if either team didn't lose
            if match_result.result_type == 'draw':
                return BetOutcome.WIN.value
            else:
                return BetOutcome.LOSE.value


class Bet(BaseModel):
    """Betting opportunity result"""

    match_id: int | None = Field(default=None, description='Match ID')
    home_team: str = Field(description='Home team name')
    away_team: str = Field(description='Away team name')
    league: str = Field(description='League name')
    country: str = Field(description='Country name')
    rule_name: str = Field(description='Rule that triggered the opportunity')
    rule_type: str = Field(description='Rule type identifier')
    bet_type: BetType = Field(description='Recommended bet type')
    confidence: float = Field(ge=0.0, le=1.0, description='Confidence level')
    team_analyzed: str = Field(description='Team that was analyzed')
    details: dict[str, Any] = Field(default_factory=dict, description='Additional details')
