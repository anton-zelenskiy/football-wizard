from contextlib import asynccontextmanager
from datetime import datetime

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.league_scraper import LeagueScraper
from app.api.live_scraper import LiveMatchScraper
from app.betting_rules import BettingRulesEngine
from app.db.models import BettingOpportunity, Match, Team, TelegramUser, create_tables
from app.db.storage import FootballDataStorage
from app.settings import settings
from app.telegram.bot import get_bot

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info('Starting Football Betting Analysis App')

    # Create database tables
    create_tables()
    logger.info('Database tables created')

    # Initialize components
    app.state.live_scraper = LiveMatchScraper()
    app.state.league_scraper = LeagueScraper()
    app.state.storage = FootballDataStorage()
    app.state.rules_engine = BettingRulesEngine()
    app.state.bot = get_bot()

    logger.info('App startup completed')

    yield

    # Shutdown
    logger.info('Shutting down Football Betting Analysis App')


app = FastAPI(
    title=settings.app_name,
    description='Football Betting Analysis API',
    version='1.0.0',
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.get('/')
async def root():
    """Root endpoint"""
    return {
        'app': settings.app_name,
        'version': '1.0.0',
        'status': 'running',
        'timestamp': datetime.now().isoformat(),
    }


@app.get('/health')
async def health_check():
    """Health check endpoint"""
    return {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': 'connected',
        'redis': 'connected',
    }


# New league scraping endpoints
@app.get('/leagues')
async def get_leagues():
    """Get all available leagues"""
    try:
        storage = app.state.storage
        leagues = storage.get_all_leagues()
        return [
            {
                'id': league.id,
                'name': league.name,
                'country': league.country,
                'created_at': league.created_at.isoformat(),
                'updated_at': league.updated_at.isoformat(),
            }
            for league in leagues
        ]
    except Exception as e:
        logger.error(f'Error getting leagues: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@app.get('/leagues/{league_name}/teams')
async def get_league_teams(league_name: str):
    """Get all teams for a specific league"""
    try:
        storage = app.state.storage
        teams = storage.get_league_teams(league_name)
        return [
            {
                'id': team.id,
                'name': team.name,
                'rank': team.rank,
                'games_played': team.games_played,
                'wins': team.wins,
                'draws': team.draws,
                'losses': team.losses,
                'goals_scored': team.goals_scored,
                'goals_conceded': team.goals_conceded,
                'points': team.points,
                'created_at': team.created_at.isoformat(),
                'updated_at': team.updated_at.isoformat(),
            }
            for team in teams
        ]
    except Exception as e:
        logger.error(f'Error getting teams for league {league_name}: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@app.get('/leagues/{league_name}/matches')
async def get_league_matches(league_name: str, limit: int = 50, status: str = None):
    """Get matches for a specific league"""
    try:
        storage = app.state.storage
        matches = storage.get_league_matches(league_name, limit)

        # Filter by status if provided
        if status:
            matches = [m for m in matches if m.status == status]

        return [
            {
                'id': match.id,
                'home_team': {'id': match.home_team.id, 'name': match.home_team.name},
                'away_team': {'id': match.away_team.id, 'name': match.away_team.name},
                'home_score': match.home_score,
                'away_score': match.away_score,
                'match_date': match.match_date.isoformat(),
                'season': match.season,
                'status': match.status,
                'minute': match.minute,
                'red_cards_home': match.red_cards_home,
                'red_cards_away': match.red_cards_away,
                'created_at': match.created_at.isoformat(),
                'updated_at': match.updated_at.isoformat(),
            }
            for match in matches
        ]
    except Exception as e:
        logger.error(f'Error getting matches for league {league_name}: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@app.get('/matches/live')
async def get_live_matches():
    """Get all currently live matches"""
    try:
        storage = app.state.storage
        live_matches = storage.get_recent_live_matches(minutes=5)
        return [
            {
                'id': match.id,
                'league': {
                    'id': match.league.id,
                    'name': match.league.name,
                    'country': match.league.country,
                },
                'home_team': {'id': match.home_team.id, 'name': match.home_team.name},
                'away_team': {'id': match.away_team.id, 'name': match.away_team.name},
                'home_score': match.home_score,
                'away_score': match.away_score,
                'match_date': match.match_date.isoformat(),
                'season': match.season,
                'status': match.status,
                'minute': match.minute,
                'red_cards_home': match.red_cards_home,
                'red_cards_away': match.red_cards_away,
                'created_at': match.created_at.isoformat(),
                'updated_at': match.updated_at.isoformat(),
            }
            for match in live_matches
        ]
    except Exception as e:
        logger.error(f'Error getting live matches: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@app.post('/scrape/russian-premier-league')
async def scrape_russian_premier_league():
    """Manually trigger Russian Premier League scraping"""
    try:
        league_scraper = app.state.league_scraper
        storage = app.state.storage

        logger.info('Starting Russian Premier League scraping')
        league_data = await league_scraper.scrape_russian_premier_league()

        league_name = league_data['league']
        country = league_data['country']
        standings = league_data['standings']
        matches = league_data['matches']

        # Save league if it doesn't exist
        storage.save_leagues([{'league': {'name': league_name}, 'country': {'name': country}}])

        # Save team standings
        if standings:
            storage.save_league_standings(standings, league_name)
            logger.info(f'Saved {len(standings)} team standings for {league_name}')

        # Save matches
        if matches:
            storage.save_matches(matches, league_name)
            logger.info(f'Saved {len(matches)} matches for {league_name}')

        return {
            'message': 'Russian Premier League scraping completed',
            'league': league_name,
            'country': country,
            'teams_count': len(standings),
            'matches_count': len(matches),
        }

    except Exception as e:
        logger.error(f'Error scraping Russian Premier League: {e}')
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/scrape/all-leagues')
async def scrape_all_leagues():
    """Manually trigger scraping for all monitored leagues"""
    try:
        league_scraper = app.state.league_scraper
        storage = app.state.storage

        logger.info('Starting scraping for all monitored leagues')
        all_league_data = await league_scraper.scrape_all_monitored_leagues()

        total_teams = 0
        total_matches = 0

        for league_data in all_league_data:
            league_name = league_data['league']
            country = league_data['country']
            standings = league_data['standings']
            matches = league_data['matches']

            # Save league if it doesn't exist
            storage.save_leagues([{'league': {'name': league_name}, 'country': {'name': country}}])

            # Save team standings
            if standings:
                storage.save_league_standings(standings, league_name)
                total_teams += len(standings)

            # Save matches
            if matches:
                storage.save_matches(matches, league_name)
                total_matches += len(matches)

        return {
            'message': 'All leagues scraping completed',
            'leagues_processed': len(all_league_data),
            'total_teams': total_teams,
            'total_matches': total_matches,
        }

    except Exception as e:
        logger.error(f'Error scraping all leagues: {e}')
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/stats/leagues')
async def get_league_stats():
    """Get statistics about leagues"""
    try:
        storage = app.state.storage
        leagues = storage.get_all_leagues()
        stats = []

        for league in leagues:
            teams = storage.get_league_teams(league.name)
            matches = storage.get_league_matches(league.name, limit=1000)  # Get all matches

            live_matches = [m for m in matches if m.status == 'live']
            finished_matches = [m for m in matches if m.status == 'finished']

            stats.append(
                {
                    'league': {'id': league.id, 'name': league.name, 'country': league.country},
                    'teams_count': len(teams),
                    'total_matches': len(matches),
                    'live_matches': len(live_matches),
                    'finished_matches': len(finished_matches),
                    'created_at': league.created_at.isoformat(),
                    'updated_at': league.updated_at.isoformat(),
                }
            )

        return stats
    except Exception as e:
        logger.error(f'Error getting league stats: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


# Legacy endpoints (keeping for backward compatibility)
@app.get('/api/teams')
async def get_teams(league: str = None, limit: int = 100):
    """Get teams from database"""
    try:
        query = Team.select()
        if league:
            query = query.where(Team.league == league)

        teams = query.limit(limit)

        return {
            'teams': [
                {
                    'id': team.id,
                    'api_id': team.api_id,
                    'name': team.name,
                    'league': team.league,
                    'country': team.country,
                    'rank': team.rank,
                    'games_played': team.games_played,
                    'wins': team.wins,
                    'draws': team.draws,
                    'losses': team.losses,
                    'goals_scored': team.goals_scored,
                    'goals_conceded': team.goals_conceded,
                    'points': team.points,
                }
                for team in teams
            ],
            'count': len(teams),
        }
    except Exception as e:
        logger.error('Error getting teams', error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/matches')
async def get_matches(league: str = None, status: str = None, limit: int = 100):
    """Get matches from database"""
    try:
        query = Match.select()
        if league:
            query = query.where(Match.league == league)
        if status:
            query = query.where(Match.status == status)

        matches = query.order_by(Match.match_date.desc()).limit(limit)

        return {
            'matches': [
                {
                    'id': match.id,
                    'api_id': match.api_id,
                    'home_team': match.home_team.name if match.home_team else '',
                    'away_team': match.away_team.name if match.away_team else '',
                    'league': match.league,
                    'country': match.country,
                    'home_score': match.home_score,
                    'away_score': match.away_score,
                    'match_date': match.match_date.isoformat() if match.match_date else None,
                    'status': match.status,
                    'minute': match.minute,
                    'red_cards_home': match.red_cards_home,
                    'red_cards_away': match.red_cards_away,
                }
                for match in matches
            ],
            'count': len(matches),
        }
    except Exception as e:
        logger.error('Error getting matches', error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/live-matches')
async def get_live_matches_legacy():
    """Get current live matches (legacy endpoint)"""
    try:
        storage = app.state.storage
        live_matches = storage.get_recent_live_matches(minutes=5)

        return {
            'live_matches': [
                {
                    'id': match.id,
                    'home_team': match.home_team.name,
                    'away_team': match.away_team.name,
                    'league': match.league.name,
                    'country': match.league.country,
                    'home_score': match.home_score,
                    'away_score': match.away_score,
                    'minute': match.minute,
                    'red_cards_home': match.red_cards_home,
                    'red_cards_away': match.red_cards_away,
                    'created_at': match.created_at.isoformat(),
                }
                for match in live_matches
            ],
            'count': len(live_matches),
        }
    except Exception as e:
        logger.error('Error getting live matches', error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/betting-opportunities')
async def get_betting_opportunities(active: bool = True, limit: int = 50):
    """Get betting opportunities"""
    try:
        query = BettingOpportunity.select()
        if active:
            query = query.where(BettingOpportunity.is_active)

        opportunities = query.order_by(BettingOpportunity.created_at.desc()).limit(limit)

        return {
            'opportunities': [
                {
                    'id': opp.id,
                    'match_id': opp.match_id,
                    'live_match_id': opp.live_match_id,
                    'opportunity_type': opp.opportunity_type,
                    'rule_triggered': opp.rule_triggered,
                    'confidence_score': opp.confidence_score,
                    'details': opp.get_details(),
                    'is_active': opp.is_active,
                    'created_at': opp.created_at.isoformat(),
                    'notified_at': opp.notified_at.isoformat() if opp.notified_at else None,
                }
                for opp in opportunities
            ],
            'count': len(opportunities),
        }
    except Exception as e:
        logger.error('Error getting betting opportunities', error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/analyze-live')
async def analyze_live_matches():
    """Manually trigger live match analysis"""
    try:
        live_scraper = app.state.live_scraper
        rules_engine = app.state.rules_engine

        # Scrape live matches
        live_matches = await live_scraper.scrape_all_sources()

        if not live_matches:
            return {'message': 'No live matches found', 'opportunities': []}

        # Analyze for opportunities
        opportunities = rules_engine.analyze_live_matches(live_matches)

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
                    'confidence': opp.confidence,
                    'reasoning': opp.reasoning,
                    'recommended_bet': opp.recommended_bet,
                }
                for opp in opportunities
            ],
        }
    except Exception as e:
        logger.error('Error analyzing live matches', error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/analyze-historical')
async def analyze_historical_matches():
    """Manually trigger historical match analysis"""
    try:
        rules_engine = app.state.rules_engine

        # Analyze historical matches
        opportunities = rules_engine.analyze_historical_matches()

        return {
            'message': 'Analysis completed',
            'opportunities_count': len(opportunities),
            'opportunities': [
                {
                    'rule_name': opp.rule_name,
                    'home_team': opp.home_team,
                    'away_team': opp.away_team,
                    'league': opp.league,
                    'confidence': opp.confidence,
                    'reasoning': opp.reasoning,
                    'recommended_bet': opp.recommended_bet,
                }
                for opp in opportunities
            ],
        }
    except Exception as e:
        logger.error('Error analyzing historical matches', error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/thesportsdb/teams/{league_name}')
async def get_thesportsdb_teams(league_name: str):
    """Get teams from TheSportsDB for a specific league"""
    try:
        api_client = app.state.api_client

        # Get the TheSportsDB league name
        thesportsdb_name = settings.thesportsdb_league_names.get(league_name, league_name)

        teams = await api_client.get_league_teams(thesportsdb_name)

        return {
            'league': league_name,
            'thesportsdb_name': thesportsdb_name,
            'teams': teams,
            'count': len(teams),
        }
    except Exception as e:
        logger.error(f'Error getting teams from TheSportsDB for {league_name}', error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/thesportsdb/standings/{league_name}')
async def get_thesportsdb_standings(league_name: str):
    """Get standings from TheSportsDB for a specific league"""
    try:
        api_client = app.state.api_client

        # Get the TheSportsDB league name
        thesportsdb_name = settings.thesportsdb_league_names.get(league_name, league_name)

        standings = await api_client.get_league_standings(thesportsdb_name)

        return {
            'league': league_name,
            'thesportsdb_name': thesportsdb_name,
            'standings': standings,
            'count': len(standings),
        }
    except Exception as e:
        logger.error(f'Error getting standings from TheSportsDB for {league_name}', error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/thesportsdb/team-form/{team_name}')
async def get_team_form(team_name: str, last_matches: int = 10):
    """Get team form from TheSportsDB"""
    try:
        api_client = app.state.api_client
        form = await api_client.get_team_form(team_name, last_matches)

        return {'team': team_name, 'form': form, 'count': len(form)}
    except Exception as e:
        logger.error(f'Error getting team form for {team_name}', error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/telegram-users')
async def get_telegram_users():
    """Get Telegram users (admin only)"""
    try:
        users = TelegramUser.select()

        return {
            'users': [
                {
                    'id': user.id,
                    'telegram_id': user.telegram_id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_active': user.is_active,
                    'notification_frequency': user.notification_frequency,
                    'created_at': user.created_at.isoformat(),
                }
                for user in users
            ],
            'count': len(users),
            'active_count': len([u for u in users if u.is_active]),
        }
    except Exception as e:
        logger.error('Error getting Telegram users', error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/stats')
async def get_stats():
    """Get application statistics"""
    try:
        storage = app.state.storage
        leagues = storage.get_all_leagues()

        total_teams = 0
        total_matches = 0
        live_matches = 0

        for league in leagues:
            teams = storage.get_league_teams(league.name)
            matches = storage.get_league_matches(league.name, limit=1000)
            total_teams += len(teams)
            total_matches += len(matches)
            live_matches += len([m for m in matches if m.status == 'live'])

        stats = {
            'leagues_count': len(leagues),
            'teams_count': total_teams,
            'matches_count': total_matches,
            'live_matches_count': live_matches,
            'betting_opportunities_count': BettingOpportunity.select()
            .where(BettingOpportunity.is_active)
            .count(),
            'telegram_users_count': TelegramUser.select().count(),
            'active_telegram_users_count': TelegramUser.select()
            .where(TelegramUser.is_active)
            .count(),
            'app_name': settings.app_name,
            'timestamp': datetime.now().isoformat(),
        }

        return stats
    except Exception as e:
        logger.error('Error getting stats', error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='0.0.0.0', port=8000)
