import structlog

from app.bet_rules.models import Bet
from app.bet_rules.rule_engine import BettingRulesEngine
from app.bot.notifications import send_betting_opportunity, send_daily_summary
from app.db.storage import FootballDataStorage
from app.scraper.livesport_scraper import CommonMatchData, LivesportScraper

logger = structlog.get_logger()


class BettingTasks:
    def __init__(self) -> None:
        self.rules_engine = BettingRulesEngine()
        self.storage = FootballDataStorage()

    async def daily_scheduled_analysis_task(self, ctx) -> str:
        """Daily task to analyze scheduled matches and find betting opportunities"""
        try:
            logger.info('Starting daily scheduled matches analysis')

            # Analyze scheduled matches for betting opportunities
            opportunities = self.rules_engine.analyze_scheduled_matches()

            if opportunities:
                # Save opportunities to database iteratively (with duplicate prevention)
                saved_opportunities = await self._save_opportunities_iteratively(opportunities)

                # Only send notifications for newly created opportunities
                if saved_opportunities:
                    await send_daily_summary(saved_opportunities)
                    logger.info(
                        f'Daily scheduled analysis completed: {len(saved_opportunities)} new opportunities found and notified'
                    )
                    return f'Daily scheduled analysis completed: {len(saved_opportunities)} new opportunities found'
                else:
                    logger.info(
                        'Daily scheduled analysis completed: no new opportunities (duplicates filtered)'
                    )
                    return 'Daily scheduled analysis completed: no new opportunities (duplicates filtered)'
            else:
                logger.info('Daily scheduled analysis completed: no opportunities found')
                return 'Daily scheduled analysis completed: no opportunities found'

        except Exception as e:
            logger.error('Error in daily scheduled analysis task', error=str(e))
            return f'Error in daily scheduled analysis: {str(e)}'

    async def live_matches_analysis_task(self, ctx) -> str:
        """Task to scrape live matches and analyze them for betting opportunities every 3 minutes"""
        try:
            logger.info('Starting live matches analysis')

            # First, scrape and save live matches iteratively using context manager
            async with LivesportScraper() as scraper:
                live_matches_data: list[CommonMatchData] = await scraper.scrape_live_matches()
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
        """Save betting opportunities iteratively with error handling and duplicate tracking"""
        saved_opportunities = []
        new_opportunities = 0
        duplicate_opportunities = 0

        for opp in opportunities:
            try:
                # Check if this opportunity already exists (by match_id, rule, and opportunity_type)
                existing_opportunity = self.storage._find_existing_opportunity(opp)

                if existing_opportunity:
                    duplicate_opportunities += 1
                    logger.debug(f'Duplicate opportunity skipped for match {opp.match_id}')
                    continue

                # Save new opportunity
                self.storage.save_opportunity(opp)
                saved_opportunities.append(opp)
                new_opportunities += 1

            except Exception as e:
                logger.error(f'Error saving opportunity {opp.rule_name}: {e}')
                continue

        logger.info(
            f'Saved {new_opportunities} new opportunities, skipped {duplicate_opportunities} duplicates'
        )
        return saved_opportunities

    async def refresh_league_data_task(self, ctx) -> str:
        """Refresh league standings and team statistics iteratively"""
        logger.info('Starting league data refresh task')

        try:
            total_leagues = 0
            total_standings = 0
            total_matches = 0
            total_fixtures = 0

            # Get monitored leagues from a temporary scraper instance (just for config)
            temp_scraper = LivesportScraper()
            monitored_leagues = temp_scraper.monitored_leagues

            # Process each league individually with its own context manager
            for country, leagues in monitored_leagues.items():
                for league_name in leagues:
                    try:
                        logger.info(f'Processing {country}: {league_name}')

                        # Use context manager for each individual league to minimize memory usage
                        async with LivesportScraper() as scraper:
                            # Scrape and save league data iteratively
                            league_stats = await self._process_single_league(
                                scraper, country, league_name
                            )

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

    async def _process_single_league(
        self, scraper: LivesportScraper, country: str, league_name: str
    ) -> dict[str, int]:
        """Process a single league: scrape and save all data iteratively"""
        stats = {'standings_count': 0, 'matches_count': 0, 'fixtures_count': 0}

        # Save league first
        self.storage.save_league({'league': {'name': league_name}, 'country': {'name': country}})

        # Scrape and save standings iteratively
        try:
            standings = await scraper.scrape_league_standings(country, league_name)
            if standings:
                for team in standings:
                    self.storage.save_team_standings(team, league_name, country)
                stats['standings_count'] = len(standings)
                logger.debug(f'Saved {len(standings)} team standings for {country} - {league_name}')
        except Exception as e:
            logger.error(f'Error scraping standings for {country}: {league_name}: {e}')

        # Scrape and save matches iteratively
        try:
            matches = await scraper.scrape_league_matches(country, league_name)
            if matches:
                for match in matches:
                    self.storage.save_match(match)
                stats['matches_count'] = len(matches)
                logger.debug(f'Saved {len(matches)} matches for {country} - {league_name}')
        except Exception as e:
            logger.error(f'Error scraping matches for {country}: {league_name}: {e}')

        # Scrape and save fixtures iteratively
        try:
            fixtures = await scraper.scrape_league_fixtures(country, league_name)
            if fixtures:
                for fixture in fixtures:
                    self.storage.save_match(fixture)
                stats['fixtures_count'] = len(fixtures)
                logger.debug(f'Saved {len(fixtures)} fixtures for {country} - {league_name}')
        except Exception as e:
            logger.error(f'Error scraping fixtures for {country}: {league_name}: {e}')

        return stats

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
async def daily_scheduled_analysis(ctx) -> None:
    """Daily scheduled analysis task for arq"""
    tasks = BettingTasks()
    return await tasks.daily_scheduled_analysis_task(ctx)


async def live_matches_analysis(ctx) -> None:
    """Live matches scraping and analysis task for arq"""
    tasks = BettingTasks()
    return await tasks.live_matches_analysis_task(ctx)


async def refresh_league_data(ctx) -> None:
    """League data refresh task for arq"""
    tasks = BettingTasks()
    return await tasks.refresh_league_data_task(ctx)
