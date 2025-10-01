import structlog

from app.bet_rules.structures import (
    Bet,
    BettingRule,
    ConsecutiveDrawsRule,
    ConsecutiveLossesRule,
    LiveMatchRedCardRule,
    Top5ConsecutiveLossesRule,
)
from app.db.models import Match
from app.db.storage import FootballDataStorage
from app.settings import settings

from .team_analysis import TeamAnalysisService


logger = structlog.get_logger()


class BettingRulesEngine:
    """Betting rules engine with configurable rules"""

    def __init__(self) -> None:
        self.storage = FootballDataStorage()
        self.top_teams_count = settings.top_teams_count
        self.team_analysis_service = TeamAnalysisService(
            top_teams_count=self.top_teams_count, min_consecutive_losses=3
        )

        self.rules: list[BettingRule] = [
            ConsecutiveLossesRule(),
            ConsecutiveDrawsRule(),
            Top5ConsecutiveLossesRule(),
            LiveMatchRedCardRule(),
        ]
        self.live_rule = LiveMatchRedCardRule()

    def get_rule_by_type(self, rule_type: str) -> BettingRule | None:
        """Get a rule by its type"""
        for rule in self.rules:
            if rule.rule_type == rule_type:
                return rule
        return None

    def analyze_match(self, match: Match) -> list[Bet]:
        """Analyze a single match for betting opportunities"""
        opportunities: list[Bet] = []

        # Get recent matches for both teams
        home_recent_matches = self.storage.get_team_recent_finished_matches(
            match.home_team, count=5
        )
        away_recent_matches = self.storage.get_team_recent_finished_matches(
            match.away_team, count=5
        )

        # Analyze both teams
        home_analysis = self.team_analysis_service.analyze_team_performance(
            match.home_team, 'home', home_recent_matches
        )
        away_analysis = self.team_analysis_service.analyze_team_performance(
            match.away_team, 'away', away_recent_matches
        )

        # Evaluate each rule uniformly; rules handle specific logic
        for rule in self.rules:
            opportunity = rule.evaluate_opportunity(
                match=match,
                home_analysis=home_analysis,
                away_analysis=away_analysis,
            )
            if opportunity:
                opportunities.append(opportunity)

        return opportunities
