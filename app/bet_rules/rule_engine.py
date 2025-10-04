import structlog

from app.bet_rules.structures import (
    Bet,
    BettingRule,
    ConsecutiveDrawsRule,
    ConsecutiveLossesRule,
    LiveMatchDrawRedCardRule,
    Top5ConsecutiveLossesRule,
)
from app.db.models import Match
from app.db.storage import FootballDataStorage
from app.settings import settings

from .team_analysis import MatchData, TeamAnalysisService, TeamData


logger = structlog.get_logger()


class BettingRulesEngine:
    """Betting rules engine with configurable rules"""

    def __init__(self, rounds_back: int = 5) -> None:
        self.storage = FootballDataStorage()
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

    def _convert_team_to_pydantic(self, team) -> TeamData:
        """Convert Peewee Team model to Pydantic TeamData"""
        return TeamData(id=team.id, name=team.name, rank=team.rank)

    def _convert_match_to_pydantic(self, match) -> MatchData:
        """Convert Peewee Match model to Pydantic MatchData"""
        return MatchData(
            id=match.id,
            home_team_id=match.home_team.id,
            away_team_id=match.away_team.id,
            home_score=match.home_score,
            away_score=match.away_score,
            match_date=match.match_date.isoformat() if match.match_date else None,
            status=match.status,
        )

    def analyze_match(self, match: Match) -> list[Bet]:
        """Analyze a single match for betting opportunities using season and round context"""
        opportunities: list[Bet] = []

        # Validate that match has required fields
        if not match.season or not match.round:
            logger.warning(
                f'Match {match.id} missing season or round information. '
                f'Season: {match.season}, Round: {match.round}'
            )
            return opportunities

        # Get team matches from the same season and previous rounds
        home_recent_matches = self.storage.get_team_matches_by_season_and_rounds(
            match.home_team, match.season, match.round, self.rounds_back
        )
        away_recent_matches = self.storage.get_team_matches_by_season_and_rounds(
            match.away_team, match.season, match.round, self.rounds_back
        )

        logger.debug(
            f'Analyzing match {match.home_team.name} vs {match.away_team.name} '
            f'(Season {match.season}, Round {match.round}) - '
            f'Home team: {len(home_recent_matches)} previous matches, '
            f'Away team: {len(away_recent_matches)} previous matches'
        )

        # Convert to Pydantic models
        home_team_data = self._convert_team_to_pydantic(match.home_team)
        away_team_data = self._convert_team_to_pydantic(match.away_team)
        home_matches_data = [
            self._convert_match_to_pydantic(m) for m in home_recent_matches
        ]
        away_matches_data = [
            self._convert_match_to_pydantic(m) for m in away_recent_matches
        ]

        # Analyze both teams using season-specific data
        home_analysis = self.team_analysis_service.analyze_team_performance(
            home_team_data, home_matches_data
        )
        away_analysis = self.team_analysis_service.analyze_team_performance(
            away_team_data, away_matches_data
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
