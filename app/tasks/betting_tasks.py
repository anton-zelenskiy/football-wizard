import structlog

from app.bet_rules.models import Bet
from app.bet_rules.rule_engine import BettingRulesEngine
from app.bot.notifications import send_betting_opportunity, send_daily_summary
from app.db.storage import FootballDataStorage
from app.scraper.livesport_scraper import CommonMatchData, LivesportScraper

logger = structlog.get_logger()


class BettingTasks:
    def __init__(self) -> None:
        self.scraper = LivesportScraper()
        self.rules_engine = BettingRulesEngine()
        self.storage = FootballDataStorage()

    async def daily_scheduled_analysis_task(self, ctx) -> str:
        """Daily task to analyze scheduled matches and find betting opportunities"""
        try:
            logger.info('Starting daily scheduled matches analysis')

            # Analyze scheduled matches for betting opportunities
            opportunities = self.rules_engine.analyze_scheduled_matches()

            if opportunities:
                # Save opportunities to database iteratively
                saved_opportunities = await self._save_opportunities_iteratively(opportunities)

                # Send notifications to users
                await send_daily_summary(saved_opportunities)

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

            # First, scrape and save live matches iteratively
            live_matches_data: list[CommonMatchData] = await self.scraper.scrape_live_matches()
            if live_matches_data:
                saved_count = await self._save_matches_iteratively(live_matches_data, 'live')
                logger.info(f'Saved {saved_count} live matches')

            # Analyze live matches for betting opportunities
            opportunities = self.rules_engine.analyze_live_matches()

            if opportunities:
                # Save opportunities to database iteratively
                saved_opportunities = await self._save_opportunities_iteratively(opportunities)

                # Send immediate notifications for live opportunities
                for opp in saved_opportunities:
                    await send_betting_opportunity(opp)

                logger.info(f'Live analysis completed: {len(opportunities)} opportunities found')
                return f'Live analysis completed: {len(opportunities)} opportunities found'
            else:
                logger.info('Live analysis completed: no opportunities found')
                return 'Live analysis completed: no opportunities found'

        except Exception as e:
            logger.error('Error in live matches analysis task', error=str(e))
            return f'Error in live analysis: {str(e)}'

    async def _save_opportunities_iteratively(self, opportunities: list[Bet]) -> list[Bet]:
        """Save betting opportunities iteratively with error handling"""
        saved_opportunities = []

        for opp in opportunities:
            try:
                self.storage.save_opportunity(opp)
                saved_opportunities.append(opp)
            except Exception as e:
                logger.error(f'Error saving opportunity {opp.rule_name}: {e}')
                continue

        return saved_opportunities

    async def refresh_league_data_task(self, ctx) -> str:
        """Refresh league standings and team statistics iteratively"""
        logger.info('Starting league data refresh task')

        try:
            total_leagues = 0
            total_standings = 0
            total_matches = 0
            total_fixtures = 0

            # Process each league individually to avoid memory issues
            for country, leagues in self.scraper.monitored_leagues.items():
                for league_name in leagues:
                    try:
                        logger.info(f'Processing {country}: {league_name}')

                        # Scrape and save league data iteratively
                        league_stats = await self._process_single_league(country, league_name)

                        total_leagues += 1
                        total_standings += league_stats['standings_count']
                        total_matches += league_stats['matches_count']
                        total_fixtures += league_stats['fixtures_count']

                        logger.info(
                            f'Completed {country}: {league_name} - '
                            f'Standings: {league_stats["standings_count"]}, '
                            f'Matches: {league_stats["matches_count"]}, '
                            f'Fixtures: {league_stats["fixtures_count"]}'
                        )

                    except Exception as e:
                        logger.error(f'Error processing {country}: {league_name}: {e}')
                        continue

            # Update betting outcomes for finished matches
            self.storage.update_betting_outcomes()

            logger.info('League data refresh completed successfully')
            return (
                f'Refreshed data for {total_leagues} leagues: '
                f'{total_standings} standings, {total_matches} matches, {total_fixtures} fixtures'
            )

        except Exception as e:
            logger.error(f'Error in league data refresh task: {e}')
            raise

    async def _process_single_league(self, country: str, league_name: str) -> dict[str, int]:
        """Process a single league: scrape and save all data iteratively"""
        stats = {'standings_count': 0, 'matches_count': 0, 'fixtures_count': 0}

        # Save league first
        self.storage.save_league({'league': {'name': league_name}, 'country': {'name': country}})

        # Scrape and save standings iteratively
        try:
            standings = await self.scraper.scrape_league_standings(country, league_name)
            if standings:
                for team in standings:
                    self.storage.save_team_standings(team, league_name, country)
                stats['standings_count'] = len(standings)
                logger.debug(f'Saved {len(standings)} team standings for {country} - {league_name}')
        except Exception as e:
            logger.error(f'Error scraping standings for {country}: {league_name}: {e}')

        # Scrape and save matches iteratively
        try:
            matches = await self.scraper.scrape_league_matches(country, league_name)
            if matches:
                for match in matches:
                    self.storage.save_match(match)
                stats['matches_count'] = len(matches)
                logger.debug(f'Saved {len(matches)} matches for {country} - {league_name}')
        except Exception as e:
            logger.error(f'Error scraping matches for {country}: {league_name}: {e}')

        # Scrape and save fixtures iteratively
        try:
            fixtures = await self.scraper.scrape_league_fixtures(country, league_name)
            if fixtures:
                for fixture in fixtures:
                    self.storage.save_match(fixture)
                stats['fixtures_count'] = len(fixtures)
                logger.debug(f'Saved {len(fixtures)} fixtures for {country} - {league_name}')
        except Exception as e:
            logger.error(f'Error scraping fixtures for {country}: {league_name}: {e}')

        return stats

    async def refresh_live_matches_task(self, ctx) -> str:
        """Refresh live matches data iteratively"""
        logger.info('Starting live matches refresh task')

        try:
            # Scrape live matches from all sources
            live_matches: list[CommonMatchData] = await self.scraper.scrape_live_matches()

            if live_matches:
                # Save matches iteratively
                saved_count = await self._save_matches_iteratively(live_matches, 'live')
                logger.info(f'Saved {saved_count} live matches')
                return f'Updated {saved_count} live matches'
            else:
                logger.info('No live matches found')
                return 'No live matches to update'

        except Exception as e:
            logger.error(f'Error in live matches refresh task: {e}')
            raise

    async def _save_matches_iteratively(
        self, matches: list[CommonMatchData], match_type: str
    ) -> int:
        """Save matches iteratively with error handling"""
        saved_count = 0

        for match in matches:
            try:
                self.storage.save_match(match)
                saved_count += 1
            except Exception as e:
                logger.error(
                    f'Error saving {match_type} match {match.home_team} vs {match.away_team}: {e}'
                )
                continue

        return saved_count


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
