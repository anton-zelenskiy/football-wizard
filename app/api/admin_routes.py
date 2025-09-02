"""
Admin API routes for scraping and analysis
"""

import structlog
from fastapi import APIRouter, HTTPException

from app.betting_rules import BettingRulesEngine
from app.db.models import BettingOpportunity, Match, Team, TelegramUser
from app.db.storage import FootballDataStorage
from app.settings import settings

logger = structlog.get_logger()

# Create router
router = APIRouter()

# Initialize components
storage = FootballDataStorage()
rules_engine = BettingRulesEngine()


@router.post("/scrape/russian-premier-league")
async def scrape_russian_premier_league():
    """Manually trigger Russian Premier League scraping"""
    try:
        from app.api.livesport_scraper import LivesportScraper
        scraper = LivesportScraper()

        logger.info('Starting Russian Premier League scraping')
        league_data = await scraper.scrape_russian_premier_league()

        league_name = league_data['league']
        country = league_data['country']
        standings = league_data['standings']
        matches = league_data['matches']
        fixtures = league_data.get('fixtures', [])

        # Save league if it doesn't exist
        storage.save_leagues([{'league': {'name': league_name}, 'country': {'name': country}}])

        # Save team standings
        if standings:
            storage.save_league_standings(standings, league_name, country)
            logger.info(f'Saved {len(standings)} team standings for {country} - {league_name}')

        # Save matches
        if matches:
            storage.save_matches(matches, league_name, country)
            logger.info(f'Saved {len(matches)} matches for {country} - {league_name}')

        # Save fixtures
        if fixtures:
            storage.save_fixtures(fixtures, league_name, country)
            logger.info(f'Saved {len(fixtures)} fixtures for {country} - {league_name}')

        return {
            'message': 'Russian Premier League scraping completed',
            'league': league_name,
            'country': country,
            'teams_count': len(standings),
            'matches_count': len(matches),
            'fixtures_count': len(fixtures),
        }

    except Exception as e:
        logger.error(f'Error scraping Russian Premier League: {e}')
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scrape/all-leagues")
async def scrape_all_leagues():
    """Manually trigger scraping for all monitored leagues"""
    try:
        from app.api.livesport_scraper import LivesportScraper
        scraper = LivesportScraper()

        logger.info('Starting scraping for all monitored leagues')
        all_league_data = await scraper.scrape_all_monitored_leagues()

        total_teams = 0
        total_matches = 0
        total_fixtures = 0

        for league_data in all_league_data:
            league_name = league_data['league']
            country = league_data['country']
            standings = league_data['standings']
            matches = league_data['matches']
            fixtures = league_data.get('fixtures', [])

            # Save league if it doesn't exist
            storage.save_leagues([{'league': {'name': league_name}, 'country': {'name': country}}])

            # Save team standings
            if standings:
                storage.save_league_standings(standings, league_name, country)
                total_teams += len(standings)

            # Save matches
            if matches:
                storage.save_matches(matches, league_name, country)
                total_matches += len(matches)

            # Save fixtures
            if fixtures:
                storage.save_fixtures(fixtures, league_name, country)
                total_fixtures += len(fixtures)

        return {
            'message': 'All leagues scraping completed',
            'leagues_processed': len(all_league_data),
            'total_teams': total_teams,
            'total_matches': total_matches,
            'total_fixtures': total_fixtures,
        }

    except Exception as e:
        logger.error(f'Error scraping all leagues: {e}')
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/analyze-live")
async def analyze_live_matches():
    """Manually trigger live match analysis"""
    try:
        from app.api.livesport_scraper import LivesportScraper
        scraper = LivesportScraper()

        # Scrape live matches
        live_matches = await scraper.scrape_live_matches()

        if not live_matches:
            return {'message': 'No live matches found', 'opportunities': []}

        # Analyze for opportunities
        opportunities = rules_engine.analyze_live_matches()

        return {
            'message': 'Analysis completed',
            'live_matches_count': len(live_matches),
            'opportunities_count': len(opportunities),
            'opportunities': [
                {
                    'rule_name': opp.rule_name,
                    'home_team': opp.home_team,
                    'away_team': opp.away_team,
                    'league': opp.league,
                    'country': opp.country,
                    'confidence': opp.confidence,
                    'details': opp.details,
                }
                for opp in opportunities
            ],
        }
    except Exception as e:
        logger.error('Error analyzing live matches', error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/analyze-historical")
async def analyze_historical_matches():
    """Manually trigger scheduled match analysis"""
    try:
        # Analyze scheduled matches
        opportunities = rules_engine.analyze_scheduled_matches()

        return {
            'message': 'Analysis completed',
            'opportunities_count': len(opportunities),
            'opportunities': [
                {
                    'rule_name': opp.rule_name,
                    'home_team': opp.home_team,
                    'away_team': opp.away_team,
                    'league': opp.league,
                    'country': opp.country,
                    'confidence': opp.confidence,
                    'details': opp.details,
                }
                for opp in opportunities
            ],
        }
    except Exception as e:
        logger.error('Error analyzing scheduled matches', error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) 