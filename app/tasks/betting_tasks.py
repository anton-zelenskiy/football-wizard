import structlog

from app.bet_rules.bet_rules import Bet
from app.bet_rules.rule_engine import BettingRulesEngine
from app.bet_rules.structures import MatchSummary
from app.bot.notifications import (
    send_betting_opportunity,
    send_coach_change_notification,
    send_daily_summary,
)
from app.db.repositories.betting_opportunity_repository import (
    BettingOpportunityRepository,
)
from app.db.repositories.league_repository import LeagueRepository
from app.db.repositories.match_repository import MatchRepository
from app.db.repositories.team_repository import TeamRepository
from app.db.session import get_async_db_session
from app.scraper.livesport_scraper import CommonMatchData, LivesportScraper


logger = structlog.get_logger()


class BettingTasks:
    def __init__(self) -> None:
        self.rules_engine = BettingRulesEngine()
        self.match_repo = None

    async def daily_scheduled_analysis_task(self, ctx) -> None:
        """Daily task to analyze scheduled matches and find betting opportunities"""
        try:
            logger.info('Starting daily scheduled matches analysis')

            # Initialize repository
            async with get_async_db_session() as session:
                self.match_repo = MatchRepository(session)

                scheduled_matches = await self.match_repo.get_matches_by_status(
                    'scheduled'
                )
                all_opportunities = []

                for match in scheduled_matches:
                    try:
                        match_summary = (
                            await self._create_match_summary_with_recent_matches(match)
                        )
                        match_opportunities = self.rules_engine.analyze_match(
                            match_summary
                        )
                        all_opportunities.extend(match_opportunities)

                    except Exception as e:
                        logger.error(
                            f'Error analyzing scheduled match {match.home_team.name} vs '
                            f'{match.away_team.name}',
                            error=str(e),
                        )

                if all_opportunities:
                    # Save opportunities to database iteratively (with duplicate prevention)
                    saved_opportunities_data = (
                        await self._save_opportunities_iteratively(all_opportunities)
                    )

                    # Only send notifications for newly created opportunities
                    if saved_opportunities_data:
                        # Extract just the Bet objects for daily summary
                        saved_opportunities = [
                            opp for opp, _ in saved_opportunities_data
                        ]
                        await send_daily_summary(saved_opportunities)
                        logger.info(
                            f'Daily scheduled analysis completed: {len(saved_opportunities)} new opportunities found and notified'
                        )
                    else:
                        logger.info(
                            'Daily scheduled analysis completed: no new opportunities (duplicates filtered)'
                        )
                else:
                    logger.info(
                        'Daily scheduled analysis completed: no opportunities found'
                    )

        except Exception as e:
            logger.error('Error in daily scheduled analysis task', error=str(e))
            return f'Error in daily scheduled analysis: {str(e)}'

    async def live_matches_analysis_task(self, ctx) -> str:
        """Task to scrape live matches and analyze them for betting opportunities every 3 minutes"""
        try:
            logger.info('Starting live matches analysis')

            # First, scrape and save live matches iteratively using context manager
            async with LivesportScraper() as scraper:
                live_matches_data: list[
                    CommonMatchData
                ] = await scraper.scrape_live_matches()

            if not live_matches_data:
                logger.info('No live matches found')
                return 'No live matches found'

            saved_count = await self._save_matches_iteratively(
                live_matches_data, 'live'
            )
            logger.info(f'Saved {saved_count} live matches')

            # Initialize repository and get live matches
            async with get_async_db_session() as session:
                self.match_repo = MatchRepository(session)

                # Get live matches and analyze each one
                live_matches = await self.match_repo.get_matches_by_status('live')
                all_opportunities = []

                for match in live_matches:
                    try:
                        # Convert Match to MatchSummary and populate recent matches
                        match_summary = (
                            await self._create_match_summary_with_recent_matches(match)
                        )
                        match_opportunities = self.rules_engine.analyze_match(
                            match_summary
                        )
                        all_opportunities.extend(match_opportunities)

                    except Exception as e:
                        logger.error(
                            f'Error analyzing live match {match.home_team.name} vs {match.away_team.name}',
                            error=str(e),
                        )

                if all_opportunities:
                    # Save opportunities to database iteratively
                    saved_opportunities_data = (
                        await self._save_opportunities_iteratively(all_opportunities)
                    )

                    # Send immediate notifications for live opportunities with duplicate prevention
                    for opp, opportunity_id in saved_opportunities_data:
                        try:
                            if opportunity_id:
                                await send_betting_opportunity(opp, opportunity_id)
                            else:
                                # Fallback to sending without duplicate check if opportunity_id is None
                                await send_betting_opportunity(opp)
                        except Exception as e:
                            logger.error(
                                f'Error sending notification for opportunity {opp.rule_name}: {e}'
                            )
                            continue

                    logger.info(
                        f'Live analysis completed: {len(all_opportunities)} opportunities found'
                    )
                    return f'Live analysis completed: {len(all_opportunities)} opportunities found'
                else:
                    logger.info('Live analysis completed: no opportunities found')
                    return 'Live analysis completed: no opportunities found'

        except Exception as e:
            logger.error('Error in live matches analysis task', error=str(e))
            return f'Error in live analysis: {str(e)}'

    async def _save_opportunities_iteratively(
        self, opportunities: list[Bet]
    ) -> list[tuple[Bet, int | None]]:
        """Save betting opportunities iteratively with error handling and duplicate tracking"""
        saved_opportunities = []
        new_opportunities = 0
        duplicate_opportunities = 0

        # Initialize repository for saving opportunities
        async with get_async_db_session() as session:
            opp_repo = BettingOpportunityRepository(session)

            for opp in opportunities:
                try:
                    # Save new opportunity using repository (includes duplicate prevention)
                    db_opportunity = await opp_repo.save_opportunity(opp)
                    saved_opportunities.append((opp, db_opportunity.id))
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
            all_coach_changes = []

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
                        all_coach_changes.extend(league_stats['coach_changes'])

                        logger.info(
                            f'Completed {country}: {league_name} - '
                            f'Standings: {league_stats["standings_count"]}, '
                            f'Matches: {league_stats["matches_count"]}, '
                            f'Fixtures: {league_stats["fixtures_count"]}, '
                            f'Coach changes: {len(league_stats["coach_changes"])}'
                        )

                    except Exception as e:
                        logger.error(f'Error processing {country}: {league_name}: {e}')
                        continue

            # Send coach change notifications
            if all_coach_changes:
                logger.info(
                    f'Found {len(all_coach_changes)} coach changes, sending notifications'
                )
                for coach_change in all_coach_changes:
                    try:
                        await send_coach_change_notification(coach_change)
                    except Exception as e:
                        logger.error(
                            f'Error sending coach change notification: {e}',
                            coach_change=coach_change,
                        )

            # Update betting outcomes for finished matches using repository
            async with get_async_db_session() as session:
                opp_repo = BettingOpportunityRepository(session)
                updated_count = await opp_repo.update_betting_outcomes()
                logger.info(f'Updated {updated_count} betting outcomes')

            logger.info('League data refresh completed successfully')
            return (
                f'Refreshed data for {total_leagues} leagues: '
                f'{total_standings} standings, {total_matches} matches, {total_fixtures} fixtures, '
                f'{len(all_coach_changes)} coach changes'
            )

        except Exception as e:
            logger.error(f'Error in league data refresh task: {e}')
            raise

    async def _process_single_league(
        self, scraper: LivesportScraper, country: str, league_name: str
    ) -> dict[str, int | list]:
        """Process a single league: scrape and save all data iteratively"""
        stats = {
            'standings_count': 0,
            'matches_count': 0,
            'fixtures_count': 0,
            'coach_changes': [],
        }

        # Save league first using repository
        async with get_async_db_session() as session:
            league_repo = LeagueRepository(session)
            await league_repo.save_league(league_name, country)

        # Scrape and save standings iteratively
        try:
            standings = await scraper.scrape_league_standings(country, league_name)
            if standings:
                # Save/update teams via repository
                async with get_async_db_session() as session:
                    team_repo = TeamRepository(session)
                    for team in standings:
                        _, coach_change = await team_repo.save_team_standings(
                            team, league_name, country
                        )
                        if coach_change:
                            stats['coach_changes'].append(coach_change)
                stats['standings_count'] = len(standings)
                logger.debug(
                    f'Saved {len(standings)} team standings for {country} - {league_name}'
                )
        except Exception as e:
            logger.error(f'Error scraping standings for {country}: {league_name}: {e}')

        # Scrape and save matches iteratively
        try:
            matches = await scraper.scrape_league_matches(country, league_name)
            if matches:
                # Initialize repository for saving matches
                async with get_async_db_session() as session:
                    match_repo = MatchRepository(session)
                    for match in matches:
                        await match_repo.save_match(match)
                stats['matches_count'] = len(matches)
                logger.debug(
                    f'Saved {len(matches)} matches for {country} - {league_name}'
                )
        except Exception as e:
            logger.error(f'Error scraping matches for {country}: {league_name}: {e}')

        # Scrape and save fixtures iteratively
        try:
            fixtures = await scraper.scrape_league_fixtures(country, league_name)
            if fixtures:
                # Initialize repository for saving fixtures
                async with get_async_db_session() as session:
                    match_repo = MatchRepository(session)
                    for fixture in fixtures:
                        await match_repo.save_match(fixture)
                stats['fixtures_count'] = len(fixtures)
                logger.debug(
                    f'Saved {len(fixtures)} fixtures for {country} - {league_name}'
                )
        except Exception as e:
            logger.error(f'Error scraping fixtures for {country}: {league_name}: {e}')

        return stats

    async def _save_matches_iteratively(
        self, matches: list[CommonMatchData], match_type: str
    ) -> int:
        """Save matches iteratively with error handling"""
        saved_count = 0

        # Initialize repository for saving matches
        async with get_async_db_session() as session:
            match_repo = MatchRepository(session)

            for match in matches:
                try:
                    await match_repo.save_match(match)
                    saved_count += 1
                except Exception as e:
                    logger.error(
                        f'Error saving {match_type} match {match.home_team} vs {match.away_team}: {e}'
                    )
                    continue

        return saved_count

    async def _create_match_summary_with_recent_matches(self, match) -> MatchSummary:
        """Create MatchSummary with populated recent matches for both teams"""
        # Get recent matches for both teams using repository
        home_recent_matches = (
            await self.match_repo.get_team_matches_by_season_and_rounds(
                match.home_team.id,
                match.season,
                match.round,
                self.rules_engine.rounds_back,
            )
        )
        away_recent_matches = (
            await self.match_repo.get_team_matches_by_season_and_rounds(
                match.away_team.id,
                match.season,
                match.round,
                self.rules_engine.rounds_back,
            )
        )

        # Convert to Pydantic models
        home_matches_data = [m.to_pydantic() for m in home_recent_matches]
        away_matches_data = [m.to_pydantic() for m in away_recent_matches]

        # Create MatchSummary with recent matches and team data
        match_summary = MatchSummary.from_match(match)
        match_summary.home_recent_matches = home_matches_data
        match_summary.away_recent_matches = away_matches_data

        # Team data is already populated by from_match method
        return match_summary


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
