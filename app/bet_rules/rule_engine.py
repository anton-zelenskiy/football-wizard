import structlog

from app.bet_rules.structures import (
    Bet,
    BettingRule,
    ConsecutiveDrawsRule,
    ConsecutiveLossesRule,
    LiveMatchDrawRedCardRule,
    MatchSummary,
    Top5ConsecutiveLossesRule,
)
from app.settings import settings

from .team_analysis import TeamAnalysisService


logger = structlog.get_logger()


class BettingRulesEngine:
    """Betting rules engine with configurable rules"""

    def __init__(self, rounds_back: int = 5) -> None:
        self.top_teams_count = settings.top_teams_count
        self.rounds_back = rounds_back
        self.team_analysis_service = TeamAnalysisService(
            top_teams_count=self.top_teams_count, min_consecutive_losses=3
        )

        self.rules: list[BettingRule] = [
            ConsecutiveLossesRule(),
            ConsecutiveDrawsRule(),
            Top5ConsecutiveLossesRule(),
            LiveMatchDrawRedCardRule(),
        ]

    def get_rule_by_slug(self, slug: str) -> BettingRule | None:
        """Get a rule by its slug"""
        for rule in self.rules:
            if rule.slug == slug:
                return rule
        return None

    def analyze_match(self, match: MatchSummary) -> list[Bet]:
        """Analyze a MatchSummary for betting opportunities using season and round context"""
        opportunities: list[Bet] = []

        # Validate that match has required fields
        if (
            not match.season
            or not match.round
            or not match.home_team_data
            or not match.away_team_data
        ):
            logger.warning(
                f'Match {match.match_id} missing required information. '
                f'Season: {match.season}, Round: {match.round}, '
                f'Home team data: {match.home_team_data is not None}, Away team data: {match.away_team_data is not None}'
            )
            return opportunities

        logger.debug(
            f'Analyzing match {match.home_team_data.name} vs {match.away_team_data.name} '
            f'(Season {match.season}, Round {match.round}) - '
            f'Home team: {len(match.home_recent_matches)} previous matches, '
            f'Away team: {len(match.away_recent_matches)} previous matches'
        )

        # Analyze both teams using the provided team data and recent matches
        home_analysis = self.team_analysis_service.analyze_team_performance(
            match.home_team_data, match.home_recent_matches
        )
        away_analysis = self.team_analysis_service.analyze_team_performance(
            match.away_team_data, match.away_recent_matches
        )

        # Evaluate each rule uniformly; rules handle specific logic
        for rule in self.rules:
            opportunity = rule.evaluate_opportunity(
                match=match,
                home_team_analysis=home_analysis,
                away_team_analysis=away_analysis,
            )
            if opportunity:
                opportunities.append(opportunity)

        return opportunities
