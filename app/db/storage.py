from datetime import datetime
from typing import Any

import structlog

from .models import League, Match, Team, db

logger = structlog.get_logger()

class FootballDataStorage:
    def __init__(self) -> None:
        self.db = db

    def save_leagues(self, leagues_data: list[dict[str, Any]]) -> None:
        """Save leagues from API data"""
        with self.db.atomic():
            for league_data in leagues_data:
                league_info = league_data.get('league', {})
                country_info = league_data.get('country', {})

                league, created = League.get_or_create(
                    name=league_info.get('name', ''),
                    defaults={
                        'country': country_info.get('name', '')
                    }
                )
                if created:
                    logger.info(f"Created new league: {league.name}")

    def save_teams(self, teams_data: list[dict[str, Any]], league_name: str) -> None:
        """Save teams from API data"""
        try:
            league = League.get(League.name == league_name)
        except League.DoesNotExist:
            logger.error(f"League not found: {league_name}")
            return

        with self.db.atomic():
            for team_data in teams_data:
                team_info = team_data.get('team', {})
                stats = team_data.get('statistics', [])

                # Extract team stats if available
                team_stats = {}
                if stats:
                    team_stats = stats[0] if isinstance(stats, list) else stats

                team, created = Team.get_or_create(
                    name=team_info.get('name', ''),
                    league=league,
                    defaults={
                        'rank': team_stats.get('rank'),
                        'games_played': team_stats.get('games', {}).get('appearences', 0),
                        'wins': team_stats.get('games', {}).get('wins', 0),
                        'draws': team_stats.get('games', {}).get('draws', 0),
                        'losses': team_stats.get('games', {}).get('loses', 0),
                        'goals_scored': team_stats.get('goals', {}).get('for', {}).get('total', 0),
                        'goals_conceded': team_stats.get('goals', {}).get('against', {}).get('total', 0),
                        'points': team_stats.get('league', {}).get('standings', [{}])[0].get('points', 0)
                    }
                )
                if created:
                    logger.info(f"Created new team: {team.name}")

    def save_matches(self, fixtures_data: list[dict[str, Any]], league_name: str) -> None:
        """Save matches from API data"""
        try:
            league = League.get(League.name == league_name)
        except League.DoesNotExist:
            logger.error(f"League not found: {league_name}")
            return

        with self.db.atomic():
            for fixture_data in fixtures_data:
                fixture = fixture_data.get('fixture', {})
                teams = fixture_data.get('teams', {})
                goals = fixture_data.get('goals', {})

                # Get or create teams
                home_team_name = teams.get('home', {}).get('name', '')
                away_team_name = teams.get('away', {}).get('name', '')

                try:
                    home_team = Team.get(Team.name == home_team_name, Team.league == league)
                    away_team = Team.get(Team.name == away_team_name, Team.league == league)
                except Team.DoesNotExist:
                    logger.warning(f"Team not found: {home_team_name} or {away_team_name}")
                    continue

                # Parse match date
                match_date_str = fixture.get('date', '')
                try:
                    match_date = datetime.fromisoformat(match_date_str.replace('Z', '+00:00'))
                except ValueError:
                    match_date = datetime.now()

                # Get scores
                home_score = goals.get('home')
                away_score = goals.get('away')

                # Determine status
                status = 'finished' if fixture.get('status', {}).get('short') == 'FT' else 'scheduled'

                match, created = Match.get_or_create(
                    league=league,
                    home_team=home_team,
                    away_team=away_team,
                    match_date=match_date,
                    defaults={
                        'home_score': home_score,
                        'away_score': away_score,
                        'season': fixture.get('league', {}).get('season', 2024),
                        'status': status
                    }
                )
                if created:
                    logger.info(f"Created new match: {home_team.name} vs {away_team.name}")

    def save_live_matches(self, live_matches_data: list[dict[str, Any]]) -> None:
        """Save live matches from scraper"""
        with self.db.atomic():
            for match_data in live_matches_data:
                # Find or create league
                league, _ = League.get_or_create(
                    name=match_data.get('league', ''),
                    defaults={'country': match_data.get('country', '')}
                )

                # Find or create teams
                home_team, _ = Team.get_or_create(
                    name=match_data.get('home_team', ''),
                    league=league
                )
                away_team, _ = Team.get_or_create(
                    name=match_data.get('away_team', ''),
                    league=league
                )

                # Check if match already exists
                try:
                    match = Match.get(
                        Match.league == league,
                        Match.home_team == home_team,
                        Match.away_team == away_team,
                        Match.status.in_(['live', 'scheduled'])
                    )
                    # Update existing match
                    match.home_score = match_data.get('home_score', 0)
                    match.away_score = match_data.get('away_score', 0)
                    match.status = 'live'
                    match.minute = match_data.get('minute')
                    match.red_cards_home = match_data.get('red_cards_home', 0)
                    match.red_cards_away = match_data.get('red_cards_away', 0)
                    match.updated_at = datetime.now()
                    match.save()
                    logger.info(f"Updated live match: {home_team.name} vs {away_team.name}")
                except Match.DoesNotExist:
                    # Create new match
                    match = Match.create(
                        league=league,
                        home_team=home_team,
                        away_team=away_team,
                        home_score=match_data.get('home_score', 0),
                        away_score=match_data.get('away_score', 0),
                        match_date=datetime.now(),
                        season=2024,
                        status='live',
                        minute=match_data.get('minute'),
                        red_cards_home=match_data.get('red_cards_home', 0),
                        red_cards_away=match_data.get('red_cards_away', 0)
                    )
                    logger.info(f"Created new live match: {home_team.name} vs {away_team.name}")

    def save_league_standings(self, standings_data: list[dict[str, Any]], league_name: str) -> None:
        """Save league standings/team statistics"""
        try:
            league = League.get(League.name == league_name)
        except League.DoesNotExist:
            logger.error(f"League not found: {league_name}")
            return

        with self.db.atomic():
            for team_data in standings_data:
                team_name = team_data.get('team', {}).get('name', '')
                if not team_name:
                    continue

                team, created = Team.get_or_create(
                    name=team_name,
                    league=league
                )

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
                    logger.info(f"Created new team: {team.name}")
                else:
                    logger.debug(f"Updated team statistics: {team.name}")

    def get_recent_live_matches(self, minutes: int = 5) -> list[Match]:
        """Get live matches from the last N minutes"""
        cutoff_time = datetime.now().replace(second=0, microsecond=0)
        return (Match
                .select()
                .where(Match.status == 'live')
                .where(Match.updated_at >= cutoff_time)
                .order_by(Match.updated_at.desc())
                .execute())

    def get_team_recent_matches(self, team_name: str, limit: int = 5) -> list[Match]:
        """Get recent matches for a specific team"""
        return (Match
                .select()
                .join(Team, on=(Match.home_team == Team.id) | (Match.away_team == Team.id))
                .where(Team.name == team_name)
                .order_by(Match.match_date.desc())
                .limit(limit)
                .execute())

    def get_league_teams(self, league_name: str) -> list[Team]:
        """Get all teams for a specific league"""
        try:
            league = League.get(League.name == league_name)
            return (Team
                    .select()
                    .where(Team.league == league)
                    .order_by(Team.rank.asc(nulls='last'))
                    .execute())
        except League.DoesNotExist:
            logger.error(f"League not found: {league_name}")
            return []

    def get_league_matches(self, league_name: str, limit: int = 50) -> list[Match]:
        """Get matches for a specific league"""
        try:
            league = League.get(League.name == league_name)
            return (Match
                    .select()
                    .where(Match.league == league)
                    .order_by(Match.match_date.desc())
                    .limit(limit)
                    .execute())
        except League.DoesNotExist:
            logger.error(f"League not found: {league_name}")
            return []

    def get_all_leagues(self) -> list[League]:
        """Get all leagues"""
        return League.select().order_by(League.name).execute()
