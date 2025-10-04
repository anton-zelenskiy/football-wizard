from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
import structlog

from app.bet_rules.structures import Bet, BetOutcome, MatchSummary
from app.db.models import (
    BettingOpportunity,
    League,
    Match,
    Team,
    db,
)
from app.scraper.livesport_scraper import CommonMatchData


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

    def save_league(self, league_data: LeagueData) -> None:
        """Save a single league from LeagueData model"""
        with self.db.atomic():
            # Normalize country name to prevent duplicates
            normalized_country = normalize_country_name(league_data.country_name)

            league, created = League.get_or_create(
                name=league_data.league_name,
                country=normalized_country,
            )
            if created:
                logger.info(f'Created new league: {league.name}')

    def update_match_status(self, match: Match, new_status: str, **kwargs: Any) -> None:
        """Update match status and related fields, handling lifecycle transitions"""
        old_status = match.status
        match.status = new_status
        match.updated_at = datetime.now()

        # Handle status-specific field updates
        if new_status == 'live':
            # Set live-specific fields
            match.minute = kwargs.get('minute')
            match.red_cards_home = kwargs.get('red_cards_home', 0)
            match.red_cards_away = kwargs.get('red_cards_away', 0)
            if 'home_score' in kwargs:
                match.home_score = kwargs['home_score']
            if 'away_score' in kwargs:
                match.away_score = kwargs['away_score']

        elif new_status == 'finished':
            # Clear live-specific fields when match finishes (set to defaults)
            match.minute = None
            match.red_cards_home = 0  # Set to default value, not None
            match.red_cards_away = 0  # Set to default value, not None
            # Ensure final scores are set
            if 'home_score' in kwargs:
                match.home_score = kwargs['home_score']
            if 'away_score' in kwargs:
                match.away_score = kwargs['away_score']

        elif new_status == 'scheduled':
            # Clear live/finished specific fields (set to defaults)
            match.minute = None
            match.red_cards_home = 0  # Set to default value, not None
            match.red_cards_away = 0  # Set to default value, not None
            match.home_score = None
            match.away_score = None

        match.save()
        logger.info(
            f'Updated match status: {match.home_team.name} vs {match.away_team.name} '
            f'{old_status} -> {new_status}'
        )

    def save_match(self, match_data: 'CommonMatchData') -> None:
        """Unified method to save any type of match (live, finished, scheduled)"""
        with self.db.atomic():
            # Normalize country name to prevent duplicates
            normalized_country = normalize_country_name(match_data.country)

            # Find or create league
            league, _ = League.get_or_create(
                name=match_data.league,
                country=normalized_country,
                defaults={'country': normalized_country},
            )

            # Find or create teams
            home_team, _ = Team.get_or_create(name=match_data.home_team, league=league)
            away_team, _ = Team.get_or_create(name=match_data.away_team, league=league)

            # Use season from match data (parsed from page)
            season = match_data.season
            round_number = match_data.round_number

            # Check if match already exists using core identifying fields
            try:
                existing_match = Match.get(
                    Match.league == league,
                    Match.home_team == home_team,
                    Match.away_team == away_team,
                    Match.season == season,
                )

                # Update existing match
                self.update_match_status(
                    existing_match,
                    match_data.status,
                    home_score=match_data.home_score,
                    away_score=match_data.away_score,
                    minute=match_data.minute,
                    red_cards_home=match_data.red_cards_home,
                    red_cards_away=match_data.red_cards_away,
                )

            except Match.DoesNotExist:
                # Create new match
                Match.create(
                    league=league,
                    home_team=home_team,
                    away_team=away_team,
                    home_score=match_data.home_score,
                    away_score=match_data.away_score,
                    match_date=match_data.match_date or datetime.now(),
                    season=season,
                    round=round_number,
                    status=match_data.status,
                    minute=match_data.minute,
                    red_cards_home=match_data.red_cards_home,
                    red_cards_away=match_data.red_cards_away,
                )
                logger.info(
                    f'Created new match: {home_team.name} vs {away_team.name} ({match_data.status})'
                )

    def save_team_standings(
        self, team_data: dict[str, Any], league_name: str, country: str
    ) -> None:
        """Save league standings/team statistics"""
        # Normalize country name to prevent duplicates
        normalized_country = normalize_country_name(country)

        try:
            league = League.get(
                (League.name == league_name) & (League.country == normalized_country)
            )
        except League.DoesNotExist:
            logger.error(f'League not found: {normalized_country} - {league_name}')
            return

        with self.db.atomic():
            team_name = team_data.get('team', {}).get('name', '')
            if not team_name:
                logger.error(f'Team not found: {team_data}')
                return

            team, created = Team.get_or_create(name=team_name, league=league)

            # Update team statistics
            team.rank = team_data.get('rank')
            team.games_played = team_data.get('all', {}).get('played', 0)
            team.wins = team_data.get('all', {}).get('win', 0)
            team.draws = team_data.get('all', {}).get('draw', 0)
            team.losses = team_data.get('all', {}).get('lose', 0)
            team.goals_scored = team_data.get('all', {}).get('goals', {}).get('for', 0)
            team.goals_conceded = (
                team_data.get('all', {}).get('goals', {}).get('against', 0)
            )
            team.points = team_data.get('points', 0)
            team.updated_at = datetime.now()
            team.save()

            if created:
                logger.info(f'Created new team: {team.name}')
            else:
                logger.debug(f'Updated team statistics: {team.name}')

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

    def save_opportunity(self, opportunity: 'Bet') -> BettingOpportunity:
        """Save betting opportunity to database with duplicate prevention"""
        match = None
        if opportunity.match_id:
            try:
                match = Match.get(Match.id == opportunity.match_id)
            except Match.DoesNotExist:
                logger.warning(
                    f'Match {opportunity.match_id} not found for betting opportunity'
                )

        # Add slug to details for outcome determination
        details = opportunity.details.copy()
        details['team_analyzed'] = opportunity.team_analyzed

        # Check for existing opportunity to prevent duplicates
        existing_opportunity = self._find_existing_opportunity(opportunity)

        if existing_opportunity:
            logger.debug(f'Opportunity already exists for match {opportunity.match_id}')
            return existing_opportunity

        # Create new opportunity
        db_opportunity = BettingOpportunity(
            match=match,
            rule_slug=opportunity.slug,
            confidence_score=opportunity.confidence,
        )
        db_opportunity.set_details(details)
        db_opportunity.save()

        logger.info(
            f'Created new betting opportunity: {opportunity.rule_name} '
            f'for match {match.id if match else "N/A"}'
        )
        return db_opportunity

    def _find_existing_opportunity(
        self, opportunity: 'Bet'
    ) -> BettingOpportunity | None:
        """Find existing betting opportunity by match_id, rule"""
        try:
            if not opportunity.match_id:
                return None

            existing = (
                BettingOpportunity.select()
                .where(
                    BettingOpportunity.match == opportunity.match_id,
                    BettingOpportunity.rule_slug == opportunity.slug,
                    BettingOpportunity.outcome.is_null(),
                )
                .first()
            )

            return existing

        except Exception as e:
            logger.error(f'Error checking for existing opportunity: {e}')
            return None

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

        match_result = MatchSummary(
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

        # Get the appropriate rule by type and determine outcome
        engine = BettingRulesEngine()
        rule = engine.get_rule_by_slug(opportunity.rule_slug)

        if rule:
            return rule.determine_outcome(match_result, team_analyzed)

        # Default: unable to determine outcome
        return None

    def get_active_betting_opportunities(self) -> list[BettingOpportunity]:
        """Get betting opportunities for upcoming matches only"""
        try:
            from datetime import datetime

            return list(
                BettingOpportunity.select()
                .join(Match, on=(BettingOpportunity.match == Match.id))
                .where(
                    (BettingOpportunity.outcome.is_null())
                    & (Match.match_date > datetime.now())
                )
                .order_by(BettingOpportunity.confidence_score.desc())
            )
        except Exception as e:
            logger.error(f'Error getting betting opportunities: {e}')
            return []

    def get_completed_betting_opportunities(
        self, limit: int = 50
    ) -> list[BettingOpportunity]:
        """Get completed betting opportunities with outcomes"""
        try:
            from datetime import datetime

            return list(
                BettingOpportunity.select()
                .join(Match, on=(BettingOpportunity.match == Match.id))
                .where(
                    (
                        BettingOpportunity.outcome.is_null(False)
                    )  # Has outcome (win/lose)
                    & (Match.match_date <= datetime.now())  # Past matches only
                )
                .order_by(Match.match_date.desc())
                .limit(limit)
            )
        except Exception as e:
            logger.error(f'Error getting completed betting opportunities: {e}')
            return []

    def get_betting_statistics(self) -> dict[str, int]:
        """Get betting statistics: total, wins, losses"""
        try:
            completed_opportunities = (
                BettingOpportunity.select()
                .join(Match, on=(BettingOpportunity.match == Match.id))
                .where(
                    (BettingOpportunity.outcome.is_null(False))  # Has outcome
                    & (Match.match_date <= datetime.now())  # Past matches only
                )
            )

            total = completed_opportunities.count()
            wins = completed_opportunities.where(
                BettingOpportunity.outcome == 'win'
            ).count()
            losses = completed_opportunities.where(
                BettingOpportunity.outcome == 'lose'
            ).count()

            return {
                'total': total,
                'wins': wins,
                'losses': losses,
                'win_rate': round((wins / total * 100) if total > 0 else 0, 1),
            }
        except Exception as e:
            logger.error(f'Error getting betting statistics: {e}')
            return {'total': 0, 'wins': 0, 'losses': 0, 'win_rate': 0.0}
