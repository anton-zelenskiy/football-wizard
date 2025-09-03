from datetime import datetime, timedelta
from typing import Any

import structlog

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

    def save_match(self, match_data: dict[str, Any]) -> None:
        """Unified method to save any type of match (live, finished, scheduled)"""
        with self.db.atomic():
            # Find or create league
            league, _ = League.get_or_create(
                name=match_data.get('league', ''),
                defaults={'country': match_data.get('country', '')},
            )

            # Find or create teams
            home_team, _ = Team.get_or_create(name=match_data.get('home_team', ''), league=league)
            away_team, _ = Team.get_or_create(name=match_data.get('away_team', ''), league=league)

            # Determine season based on status or use default
            season = match_data.get('season', 2024)
            if match_data.get('status') == 'scheduled':
                season = 2025  # Future fixtures

            round_number = match_data.get('round_number')

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
                    match_data.get('status', 'scheduled'),
                    home_score=match_data.get('home_score'),
                    away_score=match_data.get('away_score'),
                    minute=match_data.get('minute'),
                    red_cards_home=match_data.get('red_cards_home', 0),
                    red_cards_away=match_data.get('red_cards_away', 0),
                )

            except Match.DoesNotExist:
                # Create new match
                match = Match.create(
                    league=league,
                    home_team=home_team,
                    away_team=away_team,
                    home_score=match_data.get('home_score'),
                    away_score=match_data.get('away_score'),
                    match_date=match_data.get('match_date', datetime.now()),
                    season=season,
                    round=round_number,
                    status=match_data.get('status', 'scheduled'),
                    minute=match_data.get('minute'),
                    red_cards_home=match_data.get('red_cards_home', 0),
                    red_cards_away=match_data.get('red_cards_away', 0),
                )
                logger.info(
                    f'Created new match: {home_team.name} vs {away_team.name} ({match_data.get("status")})'
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

            # Update team statistics
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

    def save_fixture(self, fixture_data: dict[str, Any], league_name: str, country: str) -> None:
        """Save a single fixture - now uses the unified save_match method"""
        # Set league and country if not already set
        if not fixture_data.get('league'):
            fixture_data['league'] = league_name
        if not fixture_data.get('country'):
            fixture_data['country'] = country

        # Ensure status is set to scheduled
        fixture_data['status'] = 'scheduled'
        self.save_match(fixture_data)

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

    def _determine_betting_outcome(
        self, opportunity: BettingOpportunity, match: Match
    ) -> str | None:
        """Determine if a betting opportunity was won or lost based on the rule and match result"""
        rule_name = opportunity.rule_triggered.lower()
        home_score = match.home_score
        away_score = match.away_score

        if home_score is None or away_score is None:
            return None

        # Determine match result
        if home_score > away_score:
            match_result = 'home_win'
        elif away_score > home_score:
            match_result = 'away_win'
        else:
            match_result = 'draw'

        # Analyze rule and determine outcome
        if 'strong vs weak poor form' in rule_name:
            # This rule typically bets on the stronger team to win
            details = opportunity.get_details()
            strong_team = details.get('strong_team', '')

            if strong_team == match.home_team.name and match_result == 'home_win':
                return 'win'
            elif strong_team == match.away_team.name and match_result == 'away_win':
                return 'win'
            else:
                return 'lose'

        elif 'both teams poor form' in rule_name:
            # This rule typically bets on a draw
            return 'win' if match_result == 'draw' else 'lose'

        elif 'top team losing streak' in rule_name:
            # This rule bets on the top team to break their losing streak
            details = opportunity.get_details()
            top_team = details.get('top_team', '')

            if top_team == match.home_team.name and match_result == 'home_win':
                return 'win'
            elif top_team == match.away_team.name and match_result == 'away_win':
                return 'win'
            else:
                return 'lose'

        elif 'top team drawing streak' in rule_name:
            # This rule bets on the top team to win (break drawing streak)
            details = opportunity.get_details()
            top_team = details.get('top_team', '')

            if top_team == match.home_team.name and match_result == 'home_win':
                return 'win'
            elif top_team == match.away_team.name and match_result == 'away_win':
                return 'win'
            else:
                return 'lose'

        elif 'top team no goals' in rule_name:
            # This rule bets on the top team to score and win
            details = opportunity.get_details()
            top_team = details.get('top_team', '')

            if top_team == match.home_team.name and match_result == 'home_win':
                return 'win'
            elif top_team == match.away_team.name and match_result == 'away_win':
                return 'win'
            else:
                return 'lose'

        elif 'red card draw second half' in rule_name:
            # This rule bets on a draw in the second half
            return 'win' if match_result == 'draw' else 'lose'

        elif 'draw top5 vs below' in rule_name:
            # This rule bets on a draw when top-5 team plays below-top-5 team
            return 'win' if match_result == 'draw' else 'lose'

        # Default: unable to determine outcome
        return 'pending'
