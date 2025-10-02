from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.bet_rules.team_analysis import TeamAnalysis
from app.db.models import Match


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


class MatchResult(str, Enum):
    """Match result types"""

    INCOMPLETE = 'incomplete'
    HOME_WIN = 'home_win'
    AWAY_WIN = 'away_win'
    DRAW = 'draw'


class TeamPosition(str, Enum):
    """Team position in match"""

    HOME = 'home'
    AWAY = 'away'


class OpportunityType(str, Enum):
    """Opportunity type for betting rules"""

    HISTORICAL_ANALYSIS = BASE = 'historical_analysis'
    LIVE_OPPORTUNITY = 'live_opportunity'


class BettingRule(BaseModel):
    """Base betting rule model"""

    name: str = Field(description='Rule name')
    description: str = Field(description='Rule description')
    slug: str = Field(description='Rule type identifier')
    bet_type: BetType = Field(description='Expected bet type')
    opportunity_type: OpportunityType = Field(
        default=OpportunityType.HISTORICAL_ANALYSIS,
        description='Type of opportunity: historical_analysis or live_opportunity',
    )
    base_confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description='Base confidence level'
    )

    def calculate_confidence(
        self, team_analysis: TeamAnalysis, opponent_analysis: TeamAnalysis = None
    ) -> float:
        """Calculate confidence based on team analysis"""
        raise NotImplementedError('Subclasses must implement calculate_confidence')

    def determine_outcome(
        self, match: 'MatchSummary', team_analyzed: str
    ) -> str | None:
        """Determine if the bet was won or lost based on match result"""
        if match.result_type == MatchResult.INCOMPLETE:
            return None

        team_position = match.get_team_position(team_analyzed)

        return self._evaluate_bet_outcome(match.result_type, team_position)

    def _evaluate_bet_outcome(
        self, match_result: MatchResult, team_position: TeamPosition
    ) -> str | None:
        """Evaluate bet outcome based on match result and team position"""
        # This method should be overridden by subclasses for specific bet types
        raise NotImplementedError('Subclasses must implement _evaluate_bet_outcome')

    def evaluate_opportunity(
        self,
        match: Match,
        home_team_analysis: TeamAnalysis,
        away_team_analysis: TeamAnalysis,
    ) -> 'Bet | None':
        """Default evaluation for rules based on historical analysis.

        Subclasses can override for special live rules.
        """
        home_confidence = self.calculate_confidence(
            home_team_analysis, away_team_analysis
        )
        away_confidence = self.calculate_confidence(
            away_team_analysis, home_team_analysis
        )

        if home_confidence == 0 and away_confidence == 0:
            return None

        home_fits = home_confidence > 0
        away_fits = away_confidence > 0

        if home_fits and away_fits:
            # When both teams fit, pick the one with higher confidence
            if home_confidence >= away_confidence:
                final_confidence = home_confidence
                team_analyzed = match.home_team.name
            else:
                final_confidence = away_confidence
                team_analyzed = match.away_team.name
        elif home_fits:
            final_confidence = home_confidence
            team_analyzed = match.home_team.name
        else:
            final_confidence = away_confidence
            team_analyzed = match.away_team.name

        details: dict[str, Any] = {
            'home_team_fits': home_fits,
            'away_team_fits': away_fits,
            'home_confidence': home_confidence,
            'away_confidence': away_confidence,
            'home_team_rank': home_team_analysis.team.rank,
            'away_team_rank': away_team_analysis.team.rank,
            'home_consecutive_losses': home_team_analysis.consecutive_losses,
            'away_consecutive_losses': away_team_analysis.consecutive_losses,
            'home_consecutive_draws': home_team_analysis.consecutive_draws,
            'away_consecutive_draws': away_team_analysis.consecutive_draws,
            'home_consecutive_no_goals': home_team_analysis.consecutive_no_goals,
            'away_consecutive_no_goals': away_team_analysis.consecutive_no_goals,
            'home_is_top_5': home_team_analysis.is_top5_team,
            'away_is_top_5': away_team_analysis.is_top5_team,
            'team_analyzed': team_analyzed,
        }

        return Bet(
            match=MatchSummary.from_match(match),
            opportunity=BettingOpportunity(
                slug=self.slug,
                confidence=final_confidence,
                team_analyzed=team_analyzed,
                details=details,
            ),
        )

    def _calculate_base_confidence(self, team_analysis: TeamAnalysis) -> float:
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


class ConsecutiveLossesRule(BettingRule):
    """Rule: Team has >= 3 consecutive losses -> draw_or_win"""

    def __init__(self, **data: Any) -> None:
        super().__init__(
            name='Consecutive Losses Rule',
            description='Team with >= 3 consecutive losses -> draw_or_win',
            slug='consecutive_losses',
            bet_type=BetType.DRAW_OR_WIN,
            base_confidence=0.5,
            **data,
        )

    def calculate_confidence(
        self, team_analysis: TeamAnalysis, opponent_analysis: TeamAnalysis = None
    ) -> float:
        """Calculate confidence for consecutive losses rule"""
        if team_analysis.consecutive_losses < 3:
            return 0.0

        confidence = self._calculate_base_confidence(team_analysis)
        # Add rank-based confidence if opponent analysis is available
        if (
            opponent_analysis
            and team_analysis.team.rank
            and opponent_analysis.team.rank
        ):
            rank_difference = opponent_analysis.team.rank - team_analysis.team.rank
            if (
                rank_difference > 0
            ):  # Team we're betting on has higher rank (lower number)
                rank_bonus = 0.025 * rank_difference
                confidence += rank_bonus
                confidence = min(1.0, confidence)  # Cap at 1.0
        return confidence

    def _evaluate_bet_outcome(
        self, match_result: MatchResult, team_position: TeamPosition
    ) -> str | None:
        """Evaluate bet outcome for consecutive losses rule (draw_or_win)"""
        # For draw_or_win bet: win if the team doesn't lose (wins or draws)
        if team_position == TeamPosition.HOME:
            # Home team is the one with consecutive losses
            if match_result in [MatchResult.HOME_WIN, MatchResult.DRAW]:
                return BetOutcome.WIN.value
            else:
                return BetOutcome.LOSE.value
        else:
            # Away team is the one with consecutive losses
            if match_result in [MatchResult.AWAY_WIN, MatchResult.DRAW]:
                return BetOutcome.WIN.value
            else:
                return BetOutcome.LOSE.value


class ConsecutiveDrawsRule(BettingRule):
    """Rule: Team has >= 3 consecutive draws -> win_or_lose"""

    def __init__(self, **data: Any) -> None:
        super().__init__(
            name='Consecutive Draws Rule',
            description='Team with >= 3 consecutive draws -> win_or_lose',
            slug='consecutive_draws',
            bet_type=BetType.WIN_OR_LOSE,
            base_confidence=0.5,
            **data,
        )

    def calculate_confidence(
        self, team_analysis: TeamAnalysis, opponent_analysis: TeamAnalysis = None
    ) -> float:
        """Calculate confidence for consecutive draws rule"""
        if team_analysis.consecutive_draws < 3:
            return 0.0

        return self._calculate_base_confidence(team_analysis)

    def _evaluate_bet_outcome(
        self, match_result: MatchResult, team_position: TeamPosition
    ) -> str | None:
        """Evaluate bet outcome for consecutive draws rule (win_or_lose)"""
        # For win_or_lose bet: win if the team wins OR loses (not draw)
        if team_position == TeamPosition.HOME:
            # Home team is the one with consecutive draws
            if match_result in [MatchResult.HOME_WIN, MatchResult.AWAY_WIN]:
                return BetOutcome.WIN.value
            else:  # draw
                return BetOutcome.LOSE.value
        elif team_position == TeamPosition.AWAY:
            # Away team is the one with consecutive draws
            if match_result in [MatchResult.HOME_WIN, MatchResult.AWAY_WIN]:
                return BetOutcome.WIN.value
            else:  # draw
                return BetOutcome.LOSE.value
        else:  # TeamPosition.BOTH
            # Both teams fit the rule - check if either team won
            if match_result in [MatchResult.HOME_WIN, MatchResult.AWAY_WIN]:
                return BetOutcome.WIN.value
            else:
                return BetOutcome.LOSE.value


class Top5ConsecutiveLossesRule(BettingRule):
    """Rule: Team from top-5 and >= 2 consecutive losses -> draw_or_win"""

    def __init__(self, **data: Any) -> None:
        super().__init__(
            name='Top 5 Consecutive Losses Rule',
            description='Top 5 team with >= 2 consecutive losses -> draw_or_win',
            slug='top5_consecutive_losses',
            bet_type=BetType.DRAW_OR_WIN,
            base_confidence=0.5,
            **data,
        )

    def calculate_confidence(
        self, team_analysis: TeamAnalysis, opponent_analysis: TeamAnalysis = None
    ) -> float:
        """Calculate confidence for top 5 consecutive losses rule"""
        if not team_analysis.is_top5_team or team_analysis.consecutive_losses < 2:
            return 0.0

        return self._calculate_base_confidence(team_analysis)

    def _evaluate_bet_outcome(
        self, match_result: MatchResult, team_position: TeamPosition
    ) -> str | None:
        """Evaluate bet outcome for top-5 consecutive losses rule (draw_or_win)"""
        # For draw_or_win bet: win if the team doesn't lose (wins or draws)
        if team_position == TeamPosition.HOME:
            # Home team is the top-5 team with consecutive losses
            if match_result in [MatchResult.HOME_WIN, MatchResult.DRAW]:
                return BetOutcome.WIN.value
            else:
                return BetOutcome.LOSE.value
        else:
            # Away team is the top-5 team with consecutive losses
            if match_result in [MatchResult.AWAY_WIN, MatchResult.DRAW]:
                return BetOutcome.WIN.value
            else:
                return BetOutcome.LOSE.value


class LiveMatchRedCardRule(BettingRule):
    """Rule: Live match with red card and draw -> bet on team without red card"""

    def __init__(self, **data: Any) -> None:
        super().__init__(
            name='Live Match Red Card Rule',
            description='Live match with red card and draw -> bet on team without red card',
            slug='live_red_card',
            bet_type=BetType.WIN,
            opportunity_type=OpportunityType.LIVE_OPPORTUNITY,
            base_confidence=0.5,
            **data,
        )

    def calculate_confidence(
        self, team_analysis: TeamAnalysis, opponent_analysis: TeamAnalysis = None
    ) -> float:
        """Calculate confidence for live red card rule"""
        # This rule is only applied to live matches, not historical analysis
        return 0.0

    def calculate_live_confidence(
        self,
        home_analysis: TeamAnalysis,
        away_analysis: TeamAnalysis,
        red_cards_home: int,
        red_cards_away: int,
        home_score: int,
        away_score: int,
    ) -> tuple[float, str]:
        """Calculate confidence for live match with red cards"""
        # Only apply if there's a red card and the score is tied
        if (red_cards_home == 0 and red_cards_away == 0) or home_score != away_score:
            return 0.0, 'No red card or not a draw'

        confidence = self.base_confidence

        # Determine which team has the red card
        if red_cards_home > 0 and red_cards_away == 0:
            # Home team has red card, bet on away team
            team_analyzed = away_analysis.team.name

            # If team without red card is weaker, increase confidence
            if away_analysis.team.rank > home_analysis.team.rank:
                confidence += 0.1

            # Add confidence based on consecutive matches for team without red card
            if away_analysis.consecutive_no_goals >= 2:
                confidence += 0.05 * min(away_analysis.consecutive_no_goals - 1, 3)
            if away_analysis.consecutive_draws >= 2:
                confidence += 0.05 * min(away_analysis.consecutive_draws - 1, 2)
            if away_analysis.consecutive_losses >= 2:
                confidence += 0.05 * min(away_analysis.consecutive_losses - 1, 2)

        elif red_cards_away > 0 and red_cards_home == 0:
            # Away team has red card, bet on home team
            team_analyzed = home_analysis.team.name

            # If team without red card is weaker, increase confidence
            if home_analysis.team.rank > away_analysis.team.rank:
                confidence += 0.1

            # Add confidence based on consecutive matches for team without red card
            if home_analysis.consecutive_no_goals >= 2:
                confidence += 0.05 * min(home_analysis.consecutive_no_goals - 1, 3)
            if home_analysis.consecutive_draws >= 2:
                confidence += 0.05 * min(home_analysis.consecutive_draws - 1, 2)
            if home_analysis.consecutive_losses >= 2:
                confidence += 0.05 * min(home_analysis.consecutive_losses - 1, 2)
        else:
            return 0.0, 'Both teams have red cards or invalid state'

        return min(1.0, confidence), team_analyzed

    def evaluate_opportunity(
        self,
        match: Match,
        home_analysis: TeamAnalysis,
        away_analysis: TeamAnalysis,
    ) -> 'Bet | None':
        """Live-specific evaluation using red cards and current score."""
        confidence, team_analyzed = self.calculate_live_confidence(
            home_analysis=home_analysis,
            away_analysis=away_analysis,
            red_cards_home=match.red_cards_home,
            red_cards_away=match.red_cards_away,
            home_score=match.home_score or 0,
            away_score=match.away_score or 0,
        )

        if confidence <= 0:
            return None

        details: dict[str, Any] = {
            'live_match': True,
            'red_cards_home': match.red_cards_home,
            'red_cards_away': match.red_cards_away,
            'current_score': f'{match.home_score or 0}-{match.away_score or 0}',
            'minute': match.minute,
            'home_team_rank': home_analysis.team.rank,
            'away_team_rank': away_analysis.team.rank,
            'home_consecutive_no_goals': home_analysis.consecutive_no_goals,
            'away_consecutive_no_goals': away_analysis.consecutive_no_goals,
            'home_consecutive_draws': home_analysis.consecutive_draws,
            'away_consecutive_draws': away_analysis.consecutive_draws,
            'home_consecutive_losses': home_analysis.consecutive_losses,
            'away_consecutive_losses': away_analysis.consecutive_losses,
        }

        return Bet(
            match=MatchSummary.from_match(match),
            opportunity=BettingOpportunity(
                slug=self.slug,
                confidence=confidence,
                team_analyzed=team_analyzed,
                details=details,
            ),
        )

    def _evaluate_bet_outcome(
        self, match_result: MatchResult, team_position: TeamPosition
    ) -> str | None:
        """Evaluate bet outcome for live red card rule (win)"""
        # For live red card rule, we bet on the team without red card to win
        if team_position == TeamPosition.HOME:
            # We bet on home team to win
            if match_result == MatchResult.HOME_WIN:
                return BetOutcome.WIN.value
            else:
                return BetOutcome.LOSE.value
        elif team_position == TeamPosition.AWAY:
            # We bet on away team to win
            if match_result == MatchResult.AWAY_WIN:
                return BetOutcome.WIN.value
            else:
                return BetOutcome.LOSE.value
        else:
            return None


class MatchSummary(BaseModel):
    """Comprehensive match information for betting contexts and outcome determination"""

    match_id: int | None = Field(default=None, description='Match ID')
    home_team: str = Field(description='Home team name')
    away_team: str = Field(description='Away team name')
    league: str = Field(description='League name')
    country: str = Field(description='Country name')
    match_date: str | None = Field(default=None, description='Match date and time')
    home_score: int | None = Field(default=None, description='Home team score')
    away_score: int | None = Field(default=None, description='Away team score')

    @property
    def result_type(self) -> MatchResult:
        """Determine the match result type"""
        if self.home_score is None or self.away_score is None:
            return MatchResult.INCOMPLETE
        elif self.home_score > self.away_score:
            return MatchResult.HOME_WIN
        elif self.away_score > self.home_score:
            return MatchResult.AWAY_WIN
        return MatchResult.DRAW

    def get_team_position(self, team_analyzed: str) -> TeamPosition:
        """Determine which team position is being analyzed"""
        if team_analyzed == self.home_team:
            return TeamPosition.HOME
        return TeamPosition.AWAY

    @classmethod
    def from_match(cls, match: 'Match') -> 'MatchSummary':
        """Create MatchSummary from Match database model"""
        return cls(
            match_id=match.id,
            home_team=match.home_team.name,
            away_team=match.away_team.name,
            league=match.league.name,
            country=match.league.country,
            match_date=(
                match.match_date.strftime('%Y-%m-%d %H:%M')
                if match.match_date
                else None
            ),
            home_score=match.home_score,
            away_score=match.away_score,
        )


class BettingOpportunity(BaseModel):
    """Pure betting opportunity data without match information"""

    slug: str = Field(description='Rule slug identifier')
    confidence: float = Field(ge=0.0, le=1.0, description='Confidence level')
    team_analyzed: str = Field(description='Team that was analyzed')
    details: dict[str, Any] = Field(
        default_factory=dict, description='Additional details'
    )

    @property
    def rule(self) -> 'BettingRule | None':
        """Get the rule from the rule engine using slug"""
        from app.bet_rules.rule_engine import BettingRulesEngine

        engine = BettingRulesEngine()
        return engine.get_rule_by_slug(self.slug)

    @property
    def rule_name(self) -> str:
        """Get rule name from the rule"""
        rule = self.rule
        return rule.name if rule else 'Unknown Rule'

    @property
    def bet_type(self) -> BetType:
        """Get bet type from the rule"""
        rule = self.rule
        return rule.bet_type if rule else BetType.WIN

    @property
    def opportunity_type(self) -> OpportunityType:
        """Get opportunity type from the rule"""
        rule = self.rule
        return rule.opportunity_type if rule else OpportunityType.HISTORICAL_ANALYSIS


class Bet(BaseModel):
    """Combined betting opportunity with match information for backward compatibility"""

    match: MatchSummary = Field(description='Match information')
    opportunity: BettingOpportunity = Field(description='Betting opportunity data')

    # Backward compatibility properties
    @property
    def match_id(self) -> int | None:
        return self.match.match_id

    @property
    def home_team(self) -> str:
        return self.match.home_team

    @property
    def away_team(self) -> str:
        return self.match.away_team

    @property
    def league(self) -> str:
        return self.match.league

    @property
    def country(self) -> str:
        return self.match.country

    @property
    def match_date(self) -> str | None:
        return self.match.match_date

    @property
    def slug(self) -> str:
        return self.opportunity.slug

    @property
    def confidence(self) -> float:
        return self.opportunity.confidence

    @property
    def team_analyzed(self) -> str:
        return self.opportunity.team_analyzed

    @property
    def details(self) -> dict[str, Any]:
        return self.opportunity.details

    @property
    def rule(self) -> 'BettingRule | None':
        return self.opportunity.rule

    @property
    def rule_name(self) -> str:
        return self.opportunity.rule_name

    @property
    def bet_type(self) -> BetType:
        return self.opportunity.bet_type

    @property
    def opportunity_type(self) -> OpportunityType:
        return self.opportunity.opportunity_type

    @classmethod
    def from_legacy_data(
        cls,
        match_id: int | None,
        home_team: str,
        away_team: str,
        league: str,
        country: str,
        match_date: str | None,
        slug: str,
        confidence: float,
        team_analyzed: str,
        details: dict[str, Any],
    ) -> 'Bet':
        """Create Bet from legacy flat structure for backward compatibility"""
        match = MatchSummary(
            match_id=match_id,
            home_team=home_team,
            away_team=away_team,
            league=league,
            country=country,
            match_date=match_date,
        )
        opportunity = BettingOpportunity(
            slug=slug,
            confidence=confidence,
            team_analyzed=team_analyzed,
            details=details,
        )
        return cls(match=match, opportunity=opportunity)
