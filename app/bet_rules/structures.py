from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.bet_rules.team_analysis import MatchData, TeamAnalysis, TeamData


class BetType(str, Enum):
    """Betting outcome types"""

    WIN = 'win'
    DRAW = 'draw'
    LOSE = 'lose'
    DRAW_OR_WIN = 'draw_or_win'
    WIN_OR_LOSE = 'win_or_lose'
    GOAL = 'goal'


class MatchResult(str, Enum):
    """Match result from a team's perspective"""

    WIN = 'win'
    LOSE = 'lose'
    DRAW = 'draw'


class BetOutcome(str, Enum):
    """Betting prediction result outcomes"""

    WIN = 'win'
    LOSE = 'lose'
    UNKNOWN = 'unknown'


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
        self,
        team_analysis: TeamAnalysis,
        opponent_analysis: TeamAnalysis,
        match_summary: 'MatchSummary',
    ) -> float:
        """Calculate confidence based on team analysis"""
        raise NotImplementedError('Subclasses must implement calculate_confidence')

    def determine_outcome(
        self, match: 'MatchSummary', team_analyzed: str
    ) -> BetOutcome | None:
        """Determine if the bet was won or lost based on match result"""
        if not match.is_complete:
            return None

        return self._evaluate_bet_outcome(match, team_analyzed)

    def _evaluate_bet_outcome(
        self, match: 'MatchSummary', team_analyzed: str
    ) -> BetOutcome | None:
        """Evaluate bet outcome based on match result and team position"""
        # This method should be overridden by subclasses for specific bet types
        raise NotImplementedError('Subclasses must implement _evaluate_bet_outcome')

    def evaluate_opportunity(
        self,
        match: 'MatchSummary',
        home_team_analysis: TeamAnalysis,
        away_team_analysis: TeamAnalysis,
    ) -> 'Bet | None':
        """Default evaluation for rules based on historical analysis.

        Subclasses can override for special live rules.
        """
        match_summary = match

        home_confidence = self.calculate_confidence(
            home_team_analysis, away_team_analysis, match_summary
        )
        away_confidence = self.calculate_confidence(
            away_team_analysis, home_team_analysis, match_summary
        )

        if home_confidence == 0 and away_confidence == 0:
            return None

        home_fits = home_confidence > 0
        away_fits = away_confidence > 0

        if home_fits and away_fits:
            # When both teams fit, pick the one with higher confidence
            if home_confidence >= away_confidence:
                final_confidence = home_confidence
                team_analyzed = match.home_team_data.name
            else:
                final_confidence = away_confidence
                team_analyzed = match.away_team_data.name
        elif home_fits:
            final_confidence = home_confidence
            team_analyzed = match.home_team_data.name
        else:
            final_confidence = away_confidence
            team_analyzed = match.away_team_data.name

        details: dict[str, Any] = {
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
            'team_analyzed': team_analyzed,
        }

        return Bet(
            match=match,
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
        self,
        team_analysis: TeamAnalysis,
        opponent_analysis: TeamAnalysis,
        match_summary: 'MatchSummary' = None,
    ) -> float:
        """Calculate confidence for consecutive losses rule"""
        if team_analysis.consecutive_losses < 3:
            return 0.0

        confidence = self._calculate_base_confidence(team_analysis)

        rank_difference = opponent_analysis.team.rank - team_analysis.team.rank
        if rank_difference > 0:  # Team we're betting on has higher rank (lower number)
            rank_bonus = 0.025 * rank_difference
            confidence += rank_bonus
            confidence = min(1.0, confidence)  # Cap at 1.0
        return confidence

    def _evaluate_bet_outcome(
        self, match: 'MatchSummary', team_analyzed: str
    ) -> BetOutcome | None:
        """Evaluate bet outcome for consecutive losses rule (draw_or_win)"""
        # For draw_or_win bet: our prediction wins if the team doesn't lose (wins or draws)
        team_result = match.get_team_result(team_analyzed)
        if team_result is None:  # Incomplete match
            return None
        elif team_result in [MatchResult.WIN, MatchResult.DRAW]:
            return BetOutcome.WIN  # Our prediction was correct
        else:  # team_result == MatchResult.LOSE
            return BetOutcome.LOSE  # Our prediction was wrong


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
        self,
        team_analysis: TeamAnalysis,
        opponent_analysis: TeamAnalysis = None,
        match_summary: 'MatchSummary' = None,
    ) -> float:
        """Calculate confidence for consecutive draws rule"""
        if team_analysis.consecutive_draws < 3:
            return 0.0

        return self._calculate_base_confidence(team_analysis)

    def _evaluate_bet_outcome(
        self, match: 'MatchSummary', team_analyzed: str
    ) -> BetOutcome | None:
        """Evaluate bet outcome for consecutive draws rule (win_or_lose)"""
        # For win_or_lose bet: our prediction wins if the team wins OR loses (not draw)
        team_result = match.get_team_result(team_analyzed)
        if team_result is None:  # Incomplete match
            return None
        elif team_result in [MatchResult.WIN, MatchResult.LOSE]:
            return BetOutcome.WIN  # Our prediction was correct
        else:  # team_result == MatchResult.DRAW
            return BetOutcome.LOSE  # Our prediction was wrong


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
        self,
        team_analysis: TeamAnalysis,
        opponent_analysis: TeamAnalysis,
        match_summary: 'MatchSummary' = None,
    ) -> float:
        """Calculate confidence for top 5 consecutive losses rule"""
        if not team_analysis.is_top5_team or team_analysis.consecutive_losses < 2:
            return 0.0

        return self._calculate_base_confidence(team_analysis)

    def _evaluate_bet_outcome(
        self, match: 'MatchSummary', team_analyzed: str
    ) -> BetOutcome | None:
        """Evaluate bet outcome for top-5 consecutive losses rule (draw_or_win)"""
        # For draw_or_win bet: our prediction wins if the team doesn't lose (wins or draws)
        team_result = match.get_team_result(team_analyzed)
        if team_result is None:  # Incomplete match
            return None
        elif team_result in [MatchResult.WIN, MatchResult.DRAW]:
            return BetOutcome.WIN  # Our prediction was correct
        else:  # team_result == MatchResult.LOSE
            return BetOutcome.LOSE  # Our prediction was wrong


class LiveMatchDrawRedCardRule(BettingRule):
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
        self,
        team_analysis: TeamAnalysis,
        opponent_analysis: TeamAnalysis,
        match_summary: 'MatchSummary',
    ) -> float:
        """Calculate confidence for live red card rule"""
        # This rule requires a match summary with red card information

        # Only apply if there's a red card and the score is tied
        if (
            match_summary.red_cards_home == 0 and match_summary.red_cards_away == 0
        ) or match_summary.home_score != match_summary.away_score:
            return 0.0

        confidence = self.base_confidence

        # Determine which team has the red card
        if match_summary.red_cards_home > 0 and match_summary.red_cards_away == 0:
            # Home team has red card, bet on away team
            # Only apply if we're analyzing the away team (team without red card)
            if not opponent_analysis:
                return 0.0

            # If team without red card is weaker, increase confidence
            if team_analysis.team.rank > opponent_analysis.team.rank:
                confidence += 0.1

            # Add confidence based on consecutive matches for team without red card
            if team_analysis.consecutive_no_goals >= 2:
                confidence += 0.05 * min(team_analysis.consecutive_no_goals - 1, 3)
            if team_analysis.consecutive_draws >= 2:
                confidence += 0.05 * min(team_analysis.consecutive_draws - 1, 2)
            if team_analysis.consecutive_losses >= 2:
                confidence += 0.05 * min(team_analysis.consecutive_losses - 1, 2)

        elif match_summary.red_cards_away > 0 and match_summary.red_cards_home == 0:
            # Away team has red card, bet on home team
            # Only apply if we're analyzing the home team (team without red card)
            if not opponent_analysis:
                return 0.0

            # If team without red card is weaker, increase confidence
            if team_analysis.team.rank > opponent_analysis.team.rank:
                confidence += 0.1

            # Add confidence based on consecutive matches for team without red card
            if team_analysis.consecutive_no_goals >= 2:
                confidence += 0.05 * min(team_analysis.consecutive_no_goals - 1, 3)
            if team_analysis.consecutive_draws >= 2:
                confidence += 0.05 * min(team_analysis.consecutive_draws - 1, 2)
            if team_analysis.consecutive_losses >= 2:
                confidence += 0.05 * min(team_analysis.consecutive_losses - 1, 2)
        else:
            return 0.0

        return min(1.0, confidence)

    def evaluate_opportunity(
        self,
        match: 'MatchSummary',
        home_team_analysis: TeamAnalysis,
        away_team_analysis: TeamAnalysis,
    ) -> 'Bet | None':
        """Live-specific evaluation using red cards and current score."""
        match_summary = match

        home_confidence = self.calculate_confidence(
            home_team_analysis, away_team_analysis, match_summary
        )
        away_confidence = self.calculate_confidence(
            away_team_analysis, home_team_analysis, match_summary
        )

        if home_confidence == 0 and away_confidence == 0:
            return None

        # Determine which team to bet on based on red card situation
        if match_summary.red_cards_home > 0 and match_summary.red_cards_away == 0:
            # Home team has red card, bet on away team
            final_confidence = away_confidence
            team_analyzed = away_team_analysis.team.name
        elif match_summary.red_cards_away > 0 and match_summary.red_cards_home == 0:
            # Away team has red card, bet on home team
            final_confidence = home_confidence
            team_analyzed = home_team_analysis.team.name
        else:
            return None

        if final_confidence <= 0:
            return None

        details: dict[str, Any] = {
            'red_cards_home': match.red_cards_home,
            'red_cards_away': match.red_cards_away,
            'minute': match.minute,
            'home_team_rank': home_team_analysis.team.rank,
            'away_team_rank': away_team_analysis.team.rank,
            'home_consecutive_no_goals': home_team_analysis.consecutive_no_goals,
            'away_consecutive_no_goals': away_team_analysis.consecutive_no_goals,
            'home_consecutive_draws': home_team_analysis.consecutive_draws,
            'away_consecutive_draws': away_team_analysis.consecutive_draws,
            'home_consecutive_losses': home_team_analysis.consecutive_losses,
            'away_consecutive_losses': away_team_analysis.consecutive_losses,
        }

        return Bet(
            match=match_summary,
            opportunity=BettingOpportunity(
                slug=self.slug,
                confidence=final_confidence,
                team_analyzed=team_analyzed,
                details=details,
            ),
        )

    def _evaluate_bet_outcome(
        self, match: 'MatchSummary', team_analyzed: str
    ) -> BetOutcome | None:
        """Evaluate bet outcome for live red card rule (win)"""

        team_result = match.get_team_result(team_analyzed)
        if team_result is None:  # Incomplete match
            return None
        elif team_result == MatchResult.WIN:
            return BetOutcome.WIN
        else:
            return BetOutcome.LOSE


class MatchSummary(BaseModel):
    """Comprehensive match information for betting contexts and outcome determination"""

    match_id: int | None = Field(default=None, description='Match ID')
    home_team_data: 'TeamData' = Field(
        default=None, description='Home team data for analysis'
    )
    away_team_data: 'TeamData' = Field(
        default=None, description='Away team data for analysis'
    )
    league: str = Field(description='League name')
    country: str = Field(description='Country name')
    match_date: str | None = Field(default=None, description='Match date and time')
    home_score: int | None = Field(default=None, description='Home team score')
    away_score: int | None = Field(default=None, description='Away team score')
    red_cards_home: int = Field(default=0, description='Home team red cards')
    red_cards_away: int = Field(default=0, description='Away team red cards')
    minute: int | None = Field(
        default=None, description='Current minute for live matches'
    )
    season: int | None = Field(default=None, description='Season year')
    round: int | None = Field(default=None, description='Round number')
    home_recent_matches: list['MatchData'] = Field(
        default_factory=list, description='Home team recent matches for analysis'
    )
    away_recent_matches: list['MatchData'] = Field(
        default_factory=list, description='Away team recent matches for analysis'
    )

    @property
    def is_complete(self) -> bool:
        """Check if the match is complete (has final scores)"""
        return self.home_score is not None and self.away_score is not None

    def get_team_result(self, team_name: str) -> MatchResult | None:
        """Get the match result for a specific team (WIN/LOSE/DRAW) or None if incomplete"""
        if not self.is_complete:
            return None

        if team_name == self.home_team_data.name:
            if self.home_score > self.away_score:
                return MatchResult.WIN
            elif self.home_score < self.away_score:
                return MatchResult.LOSE
            else:
                return MatchResult.DRAW
        elif team_name == self.away_team_data.name:
            if self.away_score > self.home_score:
                return MatchResult.WIN
            elif self.away_score < self.home_score:
                return MatchResult.LOSE
            else:
                return MatchResult.DRAW

        return None  # Team not found

    @classmethod
    def from_match(cls, match) -> 'MatchSummary':
        """Create MatchSummary from Match database model"""
        return cls(
            match_id=match.id,
            home_team_data=TeamData(
                id=match.home_team.id,
                name=match.home_team.name,
                rank=match.home_team.rank,
            ),
            away_team_data=TeamData(
                id=match.away_team.id,
                name=match.away_team.name,
                rank=match.away_team.rank,
            ),
            league=match.league.name,
            country=match.league.country,
            match_date=(
                match.match_date.strftime('%Y-%m-%d %H:%M')
                if match.match_date
                else None
            ),
            home_score=match.home_score,
            away_score=match.away_score,
            red_cards_home=match.red_cards_home,
            red_cards_away=match.red_cards_away,
            minute=match.minute,
            season=match.season,
            round=match.round,
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
        return self.match.home_team_data.name

    @property
    def away_team(self) -> str:
        return self.match.away_team_data.name

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
