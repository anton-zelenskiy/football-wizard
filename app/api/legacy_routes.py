"""
Legacy API routes for backward compatibility
"""

import structlog
from fastapi import APIRouter, HTTPException

from app.db.models import BettingOpportunity, Match, Team, TelegramUser
from app.db.storage import FootballDataStorage

logger = structlog.get_logger()

# Create router
router = APIRouter()

# Initialize storage
storage = FootballDataStorage()


@router.get('/api/teams')
async def get_teams(league: str = None, limit: int = 100):
    """Get teams from database (legacy endpoint)"""
    try:
        query = Team.select()
        if league:
            query = query.where(Team.league == league)

        teams = query.limit(limit)

        return {
            'teams': [
                {
                    'id': team.id,
                    'name': team.name,
                    'league': team.league.name if team.league else None,
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


@router.get('/api/matches')
async def get_matches(league: str = None, status: str = None, limit: int = 100):
    """Get matches from database (legacy endpoint)"""
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
                    'home_team': match.home_team.name if match.home_team else '',
                    'away_team': match.away_team.name if match.away_team else '',
                    'league': match.league.name if match.league else None,
                    'country': match.league.country if match.league else None,
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


@router.get('/api/live-matches')
async def get_live_matches_legacy():
    """Get current live matches (legacy endpoint)"""
    try:
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


@router.get('/api/betting-opportunities')
async def get_betting_opportunities(active: bool = True, limit: int = 50):
    """Get betting opportunities (legacy endpoint)"""
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
                    'opportunity_type': opp.opportunity_type,
                    'rule_triggered': opp.rule_triggered,
                    'confidence_score': opp.confidence_score,
                    'details': opp.get_details(),
                    'is_active': opp.is_active,
                    'outcome': opp.outcome,
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


@router.get('/api/telegram-users')
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


@router.get('/api/stats')
async def get_stats():
    """Get application statistics (legacy endpoint)"""
    try:
        leagues = storage.get_all_leagues()

        total_teams = 0
        total_matches = 0
        live_matches = 0

        for league in leagues:
            teams = storage.get_league_teams(league.name, league.country)
            matches = storage.get_league_matches(league.name, league.country, limit=1000)
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
            'app_name': 'Football Betting Analysis',
            'timestamp': '2025-08-31T07:44:46.630748',
        }

        return stats
    except Exception as e:
        logger.error('Error getting stats', error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
