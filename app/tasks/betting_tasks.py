import structlog

from app.api.livesport_scraper import LivesportScraper, CommonMatchData
from app.betting_rules import BettingRulesEngine
from app.db.storage import FootballDataStorage
from app.telegram.bot import get_bot

logger = structlog.get_logger()


class BettingTasks:
    def __init__(self) -> None:
        self.scraper = LivesportScraper()
        self.rules_engine = BettingRulesEngine()
        self.storage = FootballDataStorage()
        self.bot = get_bot()

    async def daily_scheduled_analysis_task(self, ctx) -> str:
        """Daily task to analyze scheduled matches and find betting opportunities"""
        try:
            logger.info('Starting daily scheduled matches analysis')

            # Analyze scheduled matches for betting opportunities
            opportunities = self.rules_engine.analyze_scheduled_matches()

            if opportunities:
                # Save opportunities to database
                saved_opportunities = []
                for opp in opportunities:
                    self.rules_engine.save_opportunity(opp)
                    saved_opportunities.append(opp)

                # Send notifications to users
                # await self.bot.send_daily_summary(saved_opportunities)

                logger.info(
                    f'Daily scheduled analysis completed: {len(opportunities)} opportunities found'
                )
                return (
                    f'Daily scheduled analysis completed: {len(opportunities)} opportunities found'
                )
            else:
                logger.info('Daily scheduled analysis completed: no opportunities found')
                return 'Daily scheduled analysis completed: no opportunities found'

        except Exception as e:
            logger.error('Error in daily scheduled analysis task', error=str(e))
            return f'Error in daily scheduled analysis: {str(e)}'

    async def live_matches_analysis_task(self, ctx) -> str:
        """Task to analyze live matches for betting opportunities every 3 minutes"""
        try:
            logger.info('Starting live matches analysis')

            # First, scrape and save live matches
            live_matches_data: list[CommonMatchData] = await self.scraper.scrape_live_matches()
            if live_matches_data:
                for match in live_matches_data:
                    self.storage.save_match(match)
                logger.info(f'Saved {len(live_matches_data)} live matches')

            # Analyze live matches for betting opportunities
            opportunities = self.rules_engine.analyze_live_matches()

            if opportunities:
                # Save opportunities to database
                saved_opportunities = []
                for opp in opportunities:
                    self.rules_engine.save_opportunity(opp)
                    saved_opportunities.append(opp)

                # Send immediate notifications for live opportunities
                for opp in saved_opportunities:
                    await self.bot.send_betting_opportunity(opp)

                logger.info(f'Live analysis completed: {len(opportunities)} opportunities found')
                return f'Live analysis completed: {len(opportunities)} opportunities found'
            else:
                logger.info('Live analysis completed: no opportunities found')
                return 'Live analysis completed: no opportunities found'

        except Exception as e:
            logger.error('Error in live matches analysis task', error=str(e))
            return f'Error in live analysis: {str(e)}'

    async def refresh_league_data_task(self, ctx) -> str:
        """Refresh league standings and team statistics"""
        logger.info('Starting league data refresh task')

        try:
            # Scrape all monitored leagues
            all_league_data = await self.scraper.scrape_all_monitored_leagues()

            for league_data in all_league_data:
                league_name = league_data['league']
                country = league_data['country']
                standings = league_data['standings']
                matches: list[CommonMatchData] = league_data['matches']
                fixtures: list[CommonMatchData] = league_data.get('fixtures', [])

                logger.info(f'Processing {country}: {league_name}')

                # Save league if it doesn't exist
                self.storage.save_league(
                    {'league': {'name': league_name}, 'country': {'name': country}}
                )

                # Save team standings
                if standings:
                    for team in standings:
                        self.storage.save_team_standings(team, league_name, country)
                    logger.info(
                        f'Saved {len(standings)} team standings for {country} - {league_name}'
                    )

                # Save matches
                if matches:
                    for match in matches:
                        self.storage.save_match(match)
                    logger.info(f'Saved {len(matches)} matches for {country} - {league_name}')

                # Save fixtures
                if fixtures:
                    for fixture in fixtures:
                        self.storage.save_match(fixture)
                    logger.info(f'Saved {len(fixtures)} fixtures for {country} - {league_name}')

            # Update betting outcomes for finished matches
            self.storage.update_betting_outcomes()

            logger.info('League data refresh completed successfully')
            return f'Refreshed data for {len(all_league_data)} leagues'

        except Exception as e:
            logger.error(f'Error in league data refresh task: {e}')
            raise

    async def refresh_live_matches_task(self, ctx) -> str:
        """Refresh live matches data"""
        logger.info('Starting live matches refresh task')

        try:
            # Scrape live matches from all sources
            live_matches: list[CommonMatchData] = await self.scraper.scrape_live_matches()

            if live_matches:
                for match in live_matches:
                    self.storage.save_match(match)
                logger.info(f'Saved {len(live_matches)} live matches')
                return f'Updated {len(live_matches)} live matches'
            else:
                logger.info('No live matches found')
                return 'No live matches to update'

        except Exception as e:
            logger.error(f'Error in live matches refresh task: {e}')
            raise


# Task functions for arq
async def daily_scheduled_analysis(ctx):
    """Daily scheduled analysis task for arq"""
    tasks = BettingTasks()
    return await tasks.daily_scheduled_analysis_task(ctx)


async def live_matches_analysis(ctx):
    """Live matches analysis task for arq"""
    tasks = BettingTasks()
    return await tasks.live_matches_analysis_task(ctx)


async def refresh_league_data(ctx):
    """League data refresh task for arq"""
    tasks = BettingTasks()
    return await tasks.refresh_league_data_task(ctx)


async def refresh_live_matches(ctx):
    """Live matches refresh task for arq"""
    logger.info('Starting live matches refresh task')
    tasks = BettingTasks()
    return await tasks.refresh_live_matches_task(ctx)
