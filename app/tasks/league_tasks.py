import asyncio
from datetime import datetime
from typing import Any

import structlog
from arq import create_pool
from arq.connections import RedisSettings

from app.api.league_scraper import LeagueScraper
from app.api.live_scraper import LiveMatchScraper
from app.db.storage import FootballDataStorage
from app.settings import settings

logger = structlog.get_logger()


class LeagueTasks:
    def __init__(self) -> None:
        self.storage = FootballDataStorage()
        self.league_scraper = LeagueScraper()
        self.live_scraper = LiveMatchScraper()

    async def refresh_league_data(self, ctx: dict[str, Any]) -> str:
        """Refresh league standings and team statistics"""
        logger.info("Starting league data refresh task")

        try:
            # Scrape all monitored leagues
            all_league_data = await self.league_scraper.scrape_all_monitored_leagues()

            for league_data in all_league_data:
                league_name = league_data['league']
                country = league_data['country']
                standings = league_data['standings']
                matches = league_data['matches']

                logger.info(f"Processing {country}: {league_name}")

                # Save league if it doesn't exist
                self.storage.save_leagues([{
                    'league': {'name': league_name},
                    'country': {'name': country}
                }])

                # Save team standings
                if standings:
                    self.storage.save_league_standings(standings, league_name)
                    logger.info(f"Saved {len(standings)} team standings for {league_name}")

                # Save matches
                if matches:
                    self.storage.save_matches(matches, league_name)
                    logger.info(f"Saved {len(matches)} matches for {league_name}")

            logger.info("League data refresh completed successfully")
            return f"Refreshed data for {len(all_league_data)} leagues"

        except Exception as e:
            logger.error(f"Error in league data refresh task: {e}")
            raise

    async def refresh_live_matches(self, ctx: dict[str, Any]) -> str:
        """Refresh live matches data"""
        logger.info("Starting live matches refresh task")

        try:
            # Scrape live matches from all sources
            live_matches = await self.live_scraper.scrape_all_sources()

            if live_matches:
                self.storage.save_live_matches(live_matches)
                logger.info(f"Saved {len(live_matches)} live matches")
                return f"Updated {len(live_matches)} live matches"
            else:
                logger.info("No live matches found")
                return "No live matches to update"

        except Exception as e:
            logger.error(f"Error in live matches refresh task: {e}")
            raise

    async def refresh_russian_premier_league(self, ctx: dict[str, Any]) -> str:
        """Refresh Russian Premier League data specifically"""
        logger.info("Starting Russian Premier League refresh task")

        try:
            # Scrape Russian Premier League data
            league_data = await self.league_scraper.scrape_russian_premier_league()

            league_name = league_data['league']
            country = league_data['country']
            standings = league_data['standings']
            matches = league_data['matches']

            # Save league if it doesn't exist
            self.storage.save_leagues([{
                'league': {'name': league_name},
                'country': {'name': country}
            }])

            # Save team standings
            if standings:
                self.storage.save_league_standings(standings, league_name)
                logger.info(f"Saved {len(standings)} team standings for {league_name}")

            # Save matches
            if matches:
                self.storage.save_matches(matches, league_name)
                logger.info(f"Saved {len(matches)} matches for {league_name}")

            logger.info("Russian Premier League refresh completed successfully")
            return f"Refreshed Russian Premier League data: {len(standings)} teams, {len(matches)} matches"

        except Exception as e:
            logger.error(f"Error in Russian Premier League refresh task: {e}")
            raise

    async def daily_team_statistics_refresh(self, ctx: dict[str, Any]) -> str:
        """Daily task to refresh team statistics for all leagues"""
        logger.info("Starting daily team statistics refresh task")

        try:
            # This task runs daily to update team statistics
            # It's similar to refresh_league_data but focuses on standings
            all_league_data = await self.league_scraper.scrape_all_monitored_leagues()

            total_teams = 0
            for league_data in all_league_data:
                league_name = league_data['league']
                standings = league_data['standings']

                if standings:
                    self.storage.save_league_standings(standings, league_name)
                    total_teams += len(standings)
                    logger.info(f"Updated {len(standings)} team statistics for {league_name}")

            logger.info("Daily team statistics refresh completed successfully")
            return f"Updated statistics for {total_teams} teams across {len(all_league_data)} leagues"

        except Exception as e:
            logger.error(f"Error in daily team statistics refresh task: {e}")
            raise


# ARQ worker functions
async def refresh_league_data(ctx: dict[str, Any]) -> str:
    """ARQ worker function for league data refresh"""
    tasks = LeagueTasks()
    return await tasks.refresh_league_data(ctx)


async def refresh_live_matches(ctx: dict[str, Any]) -> str:
    """ARQ worker function for live matches refresh"""
    tasks = LeagueTasks()
    return await tasks.refresh_live_matches(ctx)


async def refresh_russian_premier_league(ctx: dict[str, Any]) -> str:
    """ARQ worker function for Russian Premier League refresh"""
    tasks = LeagueTasks()
    return await tasks.refresh_russian_premier_league(ctx)


async def daily_team_statistics_refresh(ctx: dict[str, Any]) -> str:
    """ARQ worker function for daily team statistics refresh"""
    tasks = LeagueTasks()
    return await tasks.daily_team_statistics_refresh(ctx)


# ARQ worker configuration
class WorkerSettings:
    functions = [
        refresh_league_data,
        refresh_live_matches,
        refresh_russian_premier_league,
        daily_team_statistics_refresh,
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)


async def schedule_periodic_tasks() -> None:
    """Schedule periodic tasks"""
    redis_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))

    # Schedule daily team statistics refresh at 9 AM UTC
    await redis_pool.enqueue_job(
        'daily_team_statistics_refresh',
        _defer_by=3600,  # Run in 1 hour from now
        _defer_until=datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    )

    # Schedule live matches refresh every 3 minutes
    await redis_pool.enqueue_job(
        'refresh_live_matches',
        _defer_by=180  # Run in 3 minutes
    )

    # Schedule league data refresh every 6 hours
    await redis_pool.enqueue_job(
        'refresh_league_data',
        _defer_by=21600  # Run in 6 hours
    )

    await redis_pool.close()
    logger.info("Periodic tasks scheduled")


if __name__ == '__main__':
    # Test the tasks
    async def test_tasks() -> None:
        tasks = LeagueTasks()

        # Test Russian Premier League scraping
        await tasks.refresh_russian_premier_league({})

        # Test live matches scraping
        await tasks.refresh_live_matches({})

    asyncio.run(test_tasks()) 
