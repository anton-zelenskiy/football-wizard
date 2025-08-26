import asyncio
from datetime import datetime, timedelta

import structlog
from arq.connections import RedisSettings

from app.api.espn_client import ESPNClient
from app.api.live_scraper import LiveMatchScraper
from app.betting_rules import BettingRulesEngine
from app.db.models import BettingOpportunity, Match, Team
from app.db.storage import FootballDataStorage
from app.settings import settings
from app.telegram.bot import get_bot

logger = structlog.get_logger()


class BettingTasks:
    def __init__(self) -> None:
        self.api_client = ESPNClient()
        self.live_scraper = LiveMatchScraper()
        self.rules_engine = BettingRulesEngine()
        self.bot = get_bot()
        self.storage = FootballDataStorage()

    async def daily_analysis_task(self, ctx) -> str:
        """Daily task to analyze historical matches and find betting opportunities"""
        try:
            logger.info("Starting daily betting analysis")

            # Analyze historical matches
            opportunities = self.rules_engine.analyze_historical_matches()

            if opportunities:
                # Save opportunities to database
                saved_opportunities = []
                for opp in opportunities:
                    self.rules_engine.save_opportunity(opp)
                    saved_opportunities.append(opp)

                # Send notifications to users
                await self.bot.send_daily_summary(saved_opportunities)

                logger.info(f"Daily analysis completed: {len(opportunities)} opportunities found")
                return f"Daily analysis completed: {len(opportunities)} opportunities found"
            else:
                logger.info("Daily analysis completed: no opportunities found")
                return "Daily analysis completed: no opportunities found"

        except Exception as e:
            logger.error("Error in daily analysis task", error=str(e))
            return f"Error in daily analysis: {str(e)}"

    async def live_matches_task(self, ctx) -> str:
        """Task to check live matches every 3 minutes"""
        try:
            logger.info("Starting live matches analysis")

            # Scrape live matches from all sources
            live_matches = await self.live_scraper.scrape_all_sources()

            if not live_matches:
                logger.info("No live matches found")
                return "No live matches found"

            # Save live matches to database using storage
            self.storage.save_live_matches(live_matches)

            # Analyze live matches for betting opportunities
            opportunities = self.rules_engine.analyze_live_matches(live_matches)

            if opportunities:
                # Send immediate notifications for live opportunities
                for opp in opportunities:
                    await self.bot.send_betting_opportunity(opp)

                logger.info(f"Live analysis completed: {len(opportunities)} opportunities found")
                return f"Live analysis completed: {len(opportunities)} opportunities found"
            else:
                logger.info("Live analysis completed: no opportunities found")
                return "Live analysis completed: no opportunities found"

        except Exception as e:
            logger.error("Error in live matches task", error=str(e))
            return f"Error in live analysis: {str(e)}"

    async def data_sync_task(self, ctx) -> str:
        """Task to sync data from ESPN API"""
        try:
            logger.info("Starting data sync from ESPN API")

            synced_leagues = 0
            synced_teams = 0
            synced_matches = 0

            for league_name, espn_league_id in settings.espn_league_ids.items():
                try:
                    logger.info(f"Syncing league: {league_name} ({espn_league_id})")

                    # Get teams for the league
                    teams_data = await self.api_client.get_league_teams(espn_league_id)
                    for team_data in teams_data:
                        try:
                            # Transform team data
                            transformed_team = self.api_client.transform_team_data(team_data)

                            # Create or update team
                            team, created = Team.get_or_create(
                                api_id=transformed_team['api_id'],
                                defaults={
                                    'name': transformed_team['name'],
                                    'league': league_name,
                                    'country': transformed_team['country'],
                                    'rank': None,
                                    'games_played': 0,
                                    'wins': 0,
                                    'draws': 0,
                                    'losses': 0,
                                    'goals_scored': 0,
                                    'goals_conceded': 0,
                                    'points': 0
                                }
                            )

                            if not created:
                                team.name = transformed_team['name']
                                team.league = league_name
                                team.country = transformed_team['country']
                                team.save()

                            synced_teams += 1

                        except Exception as e:
                            logger.error(f"Error processing team {team_data.get('team', {}).get('name', 'Unknown')}", error=str(e))

                    # Get league standings
                    standings_data = await self.api_client.get_league_standings(espn_league_id)
                    if standings_data:
                        transformed_standings = self.api_client.transform_standings_data(standings_data)

                        for standing in transformed_standings:
                            try:
                                team = Team.get(Team.api_id == standing['team_id'])
                                team.rank = standing['rank']
                                team.games_played = standing['games_played']
                                team.wins = standing['wins']
                                team.draws = standing['draws']
                                team.losses = standing['losses']
                                team.goals_scored = standing['goals_scored']
                                team.goals_conceded = standing['goals_conceded']
                                team.points = standing['points']
                                team.updated_at = datetime.now()
                                team.save()
                            except Team.DoesNotExist:
                                logger.warning(f"Team {standing['team_name']} not found in database")
                            except Exception as e:
                                logger.error("Error updating team standings", error=str(e))

                    # Get recent matches for the league
                    recent_matches = await self.api_client.get_league_matches(espn_league_id, status='post')
                    for match_data in recent_matches:
                        try:
                            # Transform match data
                            transformed_match = self.api_client.transform_match_data(match_data)

                            # Find home and away teams
                            home_team = None
                            away_team = None

                            if transformed_match['home_team']:
                                home_teams = Team.select().where(Team.name == transformed_match['home_team'])
                                if home_teams:
                                    home_team = home_teams[0]

                            if transformed_match['away_team']:
                                away_teams = Team.select().where(Team.name == transformed_match['away_team'])
                                if away_teams:
                                    away_team = away_teams[0]

                            if home_team and away_team:
                                # Create or update match
                                match, created = Match.get_or_create(
                                    api_id=transformed_match['api_id'],
                                    defaults={
                                        'home_team': home_team,
                                        'away_team': away_team,
                                        'league': league_name,
                                        'country': transformed_match['country'],
                                        'home_score': transformed_match['home_score'],
                                        'away_score': transformed_match['away_score'],
                                        'match_date': datetime.fromisoformat(transformed_match['match_date'].replace('Z', '+00:00')) if transformed_match['match_date'] else None,
                                        'status': 'finished' if transformed_match['home_score'] is not None else 'scheduled',
                                        'red_cards_home': 0,
                                        'red_cards_away': 0
                                    }
                                )

                                if not created:
                                    match.home_score = transformed_match['home_score']
                                    match.away_score = transformed_match['away_score']
                                    match.status = 'finished' if transformed_match['home_score'] is not None else 'scheduled'
                                    match.updated_at = datetime.now()
                                    match.save()

                                synced_matches += 1

                        except Exception as e:
                            logger.error("Error processing match", error=str(e))

                    synced_leagues += 1
                    logger.info(f"Synced league: {league_name}")

                    # Add delay to respect rate limits (ESPN has generous limits, but still be respectful)
                    await asyncio.sleep(1)

                except Exception as e:
                    logger.error(f"Error syncing league {league_name}", error=str(e))

            logger.info(f"Data sync completed: {synced_leagues} leagues, {synced_teams} teams, {synced_matches} matches")
            return f"Data sync completed: {synced_leagues} leagues, {synced_teams} teams, {synced_matches} matches"

        except Exception as e:
            logger.error("Error in data sync task", error=str(e))
            return f"Error in data sync: {str(e)}"

    async def cleanup_task(self, ctx) -> str:
        """Task to cleanup old data"""
        try:
            logger.info("Starting cleanup task")

            # Clean up old live matches (older than 24 hours)
            cutoff_time = datetime.now() - timedelta(hours=24)
            old_live_matches = Match.select().where(
                Match.status == 'live',
                Match.created_at < cutoff_time
            )
            deleted_live_matches = old_live_matches.count()
            old_live_matches.delete_instance()

            # Clean up old betting opportunities (older than 7 days)
            cutoff_time = datetime.now() - timedelta(days=7)
            old_opportunities = BettingOpportunity.select().where(BettingOpportunity.created_at < cutoff_time)
            deleted_opportunities = old_opportunities.count()
            old_opportunities.delete_instance()

            # Clean up old notification logs (older than 30 days)
            cutoff_time = datetime.now() - timedelta(days=30)
            old_notifications = NotificationLog.select().where(NotificationLog.sent_at < cutoff_time)
            deleted_notifications = old_notifications.count()
            old_notifications.delete_instance()

            logger.info(f"Cleanup completed: {deleted_live_matches} live matches, {deleted_opportunities} opportunities, {deleted_notifications} notifications")
            return f"Cleanup completed: {deleted_live_matches} live matches, {deleted_opportunities} opportunities, {deleted_notifications} notifications"

        except Exception as e:
            logger.error("Error in cleanup task", error=str(e))
            return f"Error in cleanup: {str(e)}"


# Task functions for arq
async def daily_analysis(ctx):
    """Daily analysis task for arq"""
    tasks = BettingTasks()
    return await tasks.daily_analysis_task(ctx)

async def live_matches(ctx):
    """Live matches task for arq"""
    tasks = BettingTasks()
    return await tasks.live_matches_task(ctx)

async def data_sync(ctx):
    """Data sync task for arq"""
    tasks = BettingTasks()
    return await tasks.data_sync_task(ctx)

async def cleanup(ctx):
    """Cleanup task for arq"""
    tasks = BettingTasks()
    return await tasks.cleanup_task(ctx)


# Task definitions for arq
class TaskSettings:
    functions = [daily_analysis, live_matches, data_sync, cleanup]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)

    # Schedule tasks
    cron_jobs = [
        # Daily analysis at 9 AM UTC
        ('daily_analysis', '0 9 * * *'),
        # Data sync every 6 hours
        ('data_sync', '0 */6 * * *'),
        # Cleanup every day at 2 AM UTC
        ('cleanup', '0 2 * * *'),
    ] 
