from pydantic import BaseModel, Field
import structlog

from app.bet_rules.structures import BetOutcome, MatchSummary
from app.db.models import (
    BettingOpportunity,
    Match,
    db,
)


logger = structlog.get_logger()


class LeagueData(BaseModel):
    """League data model for saving league information"""

    league_name: str = Field(description='Name of the league')
    country_name: str = Field(description='Name of the country')


def normalize_country_name(country: str) -> str:
    """Normalize country name to prevent duplicates from different case"""
    if not country:
        return country

    # Convert to title case (first letter uppercase, rest lowercase)
    return country.title()


class FootballDataStorage:
    def __init__(self) -> None:
        self.db = db

    def update_betting_outcomes(self) -> None:
        """Update betting outcomes based on finished matches"""
        # Get all pending betting opportunities for finished matches
        pending_opportunities = (
            BettingOpportunity.select()
            .join(Match, on=(BettingOpportunity.match == Match.id))
            .where(BettingOpportunity.outcome.is_null())
            .where(Match.home_score.is_null(False))
            .where(Match.away_score.is_null(False))
        )

        updated_count = 0
        for opportunity in pending_opportunities:
            logger.info(f'Processing opportunity: {opportunity.rule_slug}')
            match = opportunity.match

            # Determine outcome based on the betting rule
            outcome = self._determine_betting_outcome(opportunity, match)
            if outcome:
                opportunity.outcome = outcome.value
                opportunity.save()
                updated_count += 1
                logger.info(
                    f'Updated betting outcome: {opportunity.rule_slug} -> {outcome} '
                    f'for match {match.home_team.name} vs {match.away_team.name}'
                )

        logger.info(f'Updated {updated_count} betting outcomes')

    def _determine_betting_outcome(
        self, opportunity: BettingOpportunity, match: Match
    ) -> BetOutcome | None:
        """Determine if a betting opportunity was won or lost based on the rule and match result"""
        from app.bet_rules.rule_engine import BettingRulesEngine

        if match.status != 'finished':
            logger.warning(
                f'Match {match.id} is incomplete, skipping outcome determination'
            )
            return None

        # Get opportunity details
        details = opportunity.get_details()
        team_analyzed = details.get('team_analyzed', '')

        from app.bet_rules.team_analysis import TeamData

        match_result = MatchSummary(
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
        )

        # Get the appropriate rule by type and determine outcome
        engine = BettingRulesEngine()
        rule = engine.get_rule_by_slug(opportunity.rule_slug)

        if rule:
            return rule.determine_outcome(match_result, team_analyzed)

        # Default: unable to determine outcome
        return None
