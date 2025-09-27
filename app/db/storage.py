from datetime import datetime, timedelta
from typing import Any

import structlog

from app.bet_rules.models import (
    Bet,
    MatchResult,
)
from app.scraper.livesport_scraper import CommonMatchData

from .models import BettingOpportunity, League, Match, Team, db

logger = structlog.get_logger()


class FootballDataStorage:
    def __init__(self) -> None:
        self.db = db

    def save_league(self, league_data: dict[str, Any]) -> None:
        """Save a single league from API data"""
        with self.db.atomic():
            league_info = league_data.get('league', {})
            country_info = league_data.get('country', {})

            league, created = League.get_or_create(
                name=league_info.get('name', ''),
                country=country_info.get('name', ''),
            )
            if created:
                logger.info(f'Created new league: {league.name}')

    def update_match_status(self, match: Match, new_status: str, **kwargs) -> None:
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
            f'Updated match status: {match.home_team.name} vs {match.away_team.name} {old_status} -> {new_status}'
        )

    def save_match(self, match_data: 'CommonMatchData') -> None:
        """Unified method to save any type of match (live, finished, scheduled)"""
        with self.db.atomic():
            # Find or create league
            league, _ = League.get_or_create(
                name=match_data.league,
                country=match_data.country,
                defaults={'country': match_data.country},
            )

            # Find or create teams
            home_team, _ = Team.get_or_create(
                name=match_data.home_team, league=league, country=match_data.country
            )
            away_team, _ = Team.get_or_create(
                name=match_data.away_team, league=league, country=match_data.country
            )

            # Determine season based on status or use default
            season = 2025
            if match_data.status == 'scheduled':
                season = 2025  # Future fixtures

            round_number = match_data.round_number

            # Check if match already exists using unique constraint
            try:
                existing_match = Match.get(
                    Match.league == league,
                    Match.home_team == home_team,
                    Match.away_team == away_team,
                    Match.season == season,
                    Match.round == round_number,
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
                match = Match.create(
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
        try:
            league = League.get((League.name == league_name) & (League.country == country))
        except League.DoesNotExist:
            logger.error(f'League not found: {country} - {league_name}')
            return

        with self.db.atomic():
            team_name = team_data.get('team', {}).get('name', '')
            if not team_name:
                logger.error(f'Team not found: {team_data}')
                return

            team, created = Team.get_or_create(name=team_name, league=league)

            # Update team statistics and ensure country is set
            team.country = country  # Always set the country
            team.rank = team_data.get('rank')
            team.games_played = team_data.get('all', {}).get('played', 0)
            team.wins = team_data.get('all', {}).get('win', 0)
            team.draws = team_data.get('all', {}).get('draw', 0)
            team.losses = team_data.get('all', {}).get('lose', 0)
            team.goals_scored = team_data.get('all', {}).get('goals', {}).get('for', 0)
            team.goals_conceded = team_data.get('all', {}).get('goals', {}).get('against', 0)
            team.points = team_data.get('points', 0)
            team.updated_at = datetime.now()
            team.save()

            if created:
                logger.info(f'Created new team: {team.name}')
            else:
                logger.debug(f'Updated team statistics: {team.name}')

    def get_recent_live_matches(self, minutes: int = 5) -> list[Match]:
        """Get live matches from the last N minutes"""
        cutoff_time = datetime.now().replace(second=0, microsecond=0)
        return (
            Match.select()
            .where(Match.status == 'live')
            .where(Match.updated_at >= cutoff_time)
            .order_by(Match.updated_at.desc())
            .execute()
        )

    def get_team_recent_matches(self, team_name: str, limit: int = 5) -> list[Match]:
        """Get recent matches for a specific team"""
        return (
            Match.select()
            .join(Team, on=(Match.home_team == Team.id) | (Match.away_team == Team.id))
            .where(Team.name == team_name)
            .order_by(Match.match_date.desc())
            .limit(limit)
            .execute()
        )

    def get_team_recent_finished_matches(self, team: Team, count: int = 5) -> list[Match]:
        """Get recent finished matches for a team"""
        try:
            # Get matches where team participated
            matches = (
                Match.select()
                .where(
                    ((Match.home_team == team) | (Match.away_team == team))
                    & (Match.status == 'finished')
                )
                .order_by(Match.match_date.desc())
                .limit(count)
            )
            match_list = list(matches)
            logger.debug(
                f'Found {len(match_list)} recent matches for {team.name} (requested: {count})'
            )
            if match_list:
                logger.debug(
                    f'Most recent match: {match_list[0].home_team.name} vs {match_list[0].away_team.name} on {match_list[0].match_date}'
                )
            return match_list
        except Exception as e:
            logger.error(f'Error getting recent matches for {team.name}: {e}')
            return []

    def get_league_teams(self, league_name: str, country: str) -> list[Team]:
        """Get all teams for a specific league"""
        try:
            league = League.get((League.name == league_name) & (League.country == country))
            return (
                Team.select()
                .where(Team.league == league)
                .order_by(Team.rank.asc(nulls='last'))
                .execute()
            )
        except League.DoesNotExist:
            logger.error(f'League not found: {country} - {league_name}')
            return []

    def get_league_matches(self, league_name: str, country: str, limit: int = 50) -> list[Match]:
        """Get matches for a specific league"""
        try:
            league = League.get((League.name == league_name) & (League.country == country))
            return (
                Match.select()
                .where(Match.league == league)
                .order_by(Match.match_date.desc())
                .limit(limit)
                .join(Team, on=(Match.home_team == Team.id) | (Match.away_team == Team.id))
                .execute()
            )
        except League.DoesNotExist:
            logger.error(f'League not found: {country} - {league_name}')
            return []

    def get_league_fixtures(self, league_name: str, country: str, limit: int = 10) -> list[Match]:
        """Get upcoming fixtures for a specific league"""
        try:
            league = League.get((League.name == league_name) & (League.country == country))
            return (
                Match.select()
                .where(Match.league == league)
                .where(Match.status == 'scheduled')
                .where(Match.match_date > datetime.now())
                .order_by(Match.match_date.asc())
                .limit(limit)
                .join(Team, on=(Match.home_team == Team.id) | (Match.away_team == Team.id))
                .execute()
            )
        except League.DoesNotExist:
            logger.error(f'League not found: {country} - {league_name}')
            return []

    def get_scheduled_matches(self, days_ahead: int = 7) -> list[Match]:
        """Get all scheduled matches for the next N days"""
        cutoff_date = datetime.now() + timedelta(days=days_ahead)
        return (
            Match.select()
            .where(Match.status == 'scheduled')
            # .where(Match.match_date > datetime.now())
            # .where(Match.match_date <= cutoff_date)
            .order_by(Match.match_date.asc())
            .join(Team, on=(Match.home_team == Team.id) | (Match.away_team == Team.id))
            .execute()
        )

    def get_all_leagues(self) -> list[League]:
        """Get all leagues"""
        return League.select().order_by(League.name).execute()

    def get_match_lifecycle_summary(self) -> dict[str, int]:
        """Get summary of matches by status for monitoring purposes"""
        return {
            'scheduled': Match.select().where(Match.status == 'scheduled').count(),
            'live': Match.select().where(Match.status == 'live').count(),
            'finished': Match.select().where(Match.status == 'finished').count(),
            'total': Match.select().count(),
        }

    def update_betting_outcomes(self) -> None:
        """Update betting outcomes based on finished matches"""
        from .models import BettingOpportunity

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
            match = opportunity.match

            # Determine outcome based on the betting rule
            outcome = self._determine_betting_outcome(opportunity, match)
            if outcome:
                opportunity.outcome = outcome
                opportunity.save()
                updated_count += 1
                logger.info(
                    f'Updated betting outcome: {opportunity.rule_triggered} -> {outcome} for match {match.home_team.name} vs {match.away_team.name}'
                )

        logger.info(f'Updated {updated_count} betting outcomes')

    def save_opportunity(self, opportunity: 'Bet') -> BettingOpportunity:
        """Save betting opportunity to database"""
        match = None
        if opportunity.match_id:
            try:
                match = Match.get(Match.id == opportunity.match_id)
            except Match.DoesNotExist:
                logger.warning(f'Match {opportunity.match_id} not found for betting opportunity')

        # Determine opportunity type based on rule name
        opportunity_type = (
            'live_opportunity' if 'Live' in opportunity.rule_name else 'historical_analysis'
        )

        # Add rule_type to details for outcome determination
        details = opportunity.details.copy()
        details['rule_type'] = opportunity.rule_type
        details['team_analyzed'] = opportunity.team_analyzed

        db_opportunity = BettingOpportunity(
            match=match,
            opportunity_type=opportunity_type,
            rule_triggered=opportunity.rule_name,
            confidence_score=opportunity.confidence,
        )
        db_opportunity.set_details(details)
        db_opportunity.save()
        return db_opportunity

    def _determine_betting_outcome(
        self, opportunity: BettingOpportunity, match: Match
    ) -> str | None:
        """Determine if a betting opportunity was won or lost based on the rule and match result"""
        from app.bet_rules.rule_engine import BettingRulesEngine

        # Get opportunity details
        details = opportunity.get_details()
        team_analyzed = details.get('team_analyzed', '')
        rule_type = details.get('rule_type', '')

        # Create MatchResult DTO
        match_result = MatchResult(
            home_score=match.home_score,
            away_score=match.away_score,
            home_team=match.home_team.name,
            away_team=match.away_team.name,
            team_analyzed=team_analyzed,
        )

        # Get the appropriate rule by type and determine outcome
        engine = BettingRulesEngine()
        rule = engine.get_rule_by_type(rule_type)

        if rule:
            return rule.determine_outcome(match_result)

        # Default: unable to determine outcome
        return None

    def get_live_matches(self) -> list[Match]:
        """Get all live matches"""
        try:
            return list(Match.select().where(Match.status == 'live'))
        except Exception as e:
            logger.error(f'Error getting live matches: {e}')
            return []
