"""
Shared API routes for Football Betting Analysis
"""

from fastapi import APIRouter, HTTPException
import structlog

from app.db.storage import FootballDataStorage


logger = structlog.get_logger()

# Create router
router = APIRouter()

# Initialize storage
storage = FootballDataStorage()


@router.get("/leagues")
async def get_leagues():
    """Get all available leagues"""
    try:
        leagues = storage.get_all_leagues()
        return [
            {
                "id": league.id,
                "name": league.name,
                "country": league.country,
                "created_at": league.created_at.isoformat(),
                "updated_at": league.updated_at.isoformat(),
            }
            for league in leagues
        ]
    except Exception as e:
        logger.error(f"Error getting leagues: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/leagues/{country}/{league_name}/teams")
async def get_league_teams(country: str, league_name: str):
    """Get all teams for a specific league"""
    try:
        teams = storage.get_league_teams(league_name, country)
        return [
            {
                "id": team.id,
                "name": team.name,
                "rank": team.rank,
                "games_played": team.games_played,
                "wins": team.wins,
                "draws": team.draws,
                "losses": team.losses,
                "goals_scored": team.goals_scored,
                "goals_conceded": team.goals_conceded,
                "points": team.points,
                "created_at": team.created_at.isoformat(),
                "updated_at": team.updated_at.isoformat(),
            }
            for team in teams
        ]
    except Exception as e:
        logger.error(f"Error getting teams for league {league_name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/leagues/{country}/{league_name}/matches")
async def get_league_matches(
    country: str, league_name: str, limit: int = 50, status: str = None
):
    """Get matches for a specific league"""
    try:
        matches = storage.get_league_matches(league_name, country, limit)

        # Filter by status if provided
        if status:
            matches = [m for m in matches if m.status == status]

        return [
            {
                "id": match.id,
                "home_team": {"id": match.home_team.id, "name": match.home_team.name},
                "away_team": {"id": match.away_team.id, "name": match.away_team.name},
                "home_score": match.home_score,
                "away_score": match.away_score,
                "match_date": match.match_date.isoformat(),
                "season": match.season,
                "status": match.status,
                "minute": match.minute,
                "red_cards_home": match.red_cards_home,
                "red_cards_away": match.red_cards_away,
                "created_at": match.created_at.isoformat(),
                "updated_at": match.updated_at.isoformat(),
            }
            for match in matches
        ]
    except Exception as e:
        logger.error(f"Error getting matches for league {league_name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/leagues/{country}/{league_name}/fixtures")
async def get_league_fixtures(country: str, league_name: str, limit: int = 10):
    """Get upcoming fixtures for a specific league"""
    try:
        fixtures = storage.get_league_fixtures(league_name, country, limit)

        return [
            {
                "id": fixture.id,
                "home_team": {
                    "id": fixture.home_team.id,
                    "name": fixture.home_team.name,
                },
                "away_team": {
                    "id": fixture.away_team.id,
                    "name": fixture.away_team.name,
                },
                "home_score": fixture.home_score,
                "away_score": fixture.away_score,
                "match_date": fixture.match_date.isoformat(),
                "season": fixture.season,
                "status": fixture.status,
                "minute": fixture.minute,
                "red_cards_home": fixture.red_cards_home,
                "red_cards_away": fixture.red_cards_away,
                "created_at": fixture.created_at.isoformat(),
                "updated_at": fixture.updated_at.isoformat(),
            }
            for fixture in fixtures
        ]
    except Exception as e:
        logger.error(f"Error getting fixtures for league {league_name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/matches/live")
async def get_live_matches():
    """Get all currently live matches"""
    try:
        live_matches = storage.get_recent_live_matches(minutes=5)
        return [
            {
                "id": match.id,
                "league": {
                    "id": match.league.id,
                    "name": match.league.name,
                    "country": match.league.country,
                },
                "home_team": {"id": match.home_team.id, "name": match.home_team.name},
                "away_team": {"id": match.away_team.id, "name": match.away_team.name},
                "home_score": match.home_score,
                "away_score": match.away_score,
                "match_date": match.match_date.isoformat(),
                "season": match.season,
                "status": match.status,
                "minute": match.minute,
                "red_cards_home": match.red_cards_home,
                "red_cards_away": match.red_cards_away,
                "created_at": match.created_at.isoformat(),
                "updated_at": match.updated_at.isoformat(),
            }
            for match in live_matches
        ]
    except Exception as e:
        logger.error(f"Error getting live matches: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats/leagues")
async def get_league_stats():
    """Get statistics about leagues"""
    try:
        leagues = storage.get_all_leagues()
        stats = []

        for league in leagues:
            teams = storage.get_league_teams(league.name, league.country)
            matches = storage.get_league_matches(
                league.name, league.country, limit=1000
            )  # Get all matches

            live_matches = [m for m in matches if m.status == "live"]
            finished_matches = [m for m in matches if m.status == "finished"]

            stats.append(
                {
                    "league": {
                        "id": league.id,
                        "name": league.name,
                        "country": league.country,
                    },
                    "teams_count": len(teams),
                    "total_matches": len(matches),
                    "live_matches": len(live_matches),
                    "finished_matches": len(finished_matches),
                    "created_at": league.created_at.isoformat(),
                    "updated_at": league.updated_at.isoformat(),
                }
            )

        return stats
    except Exception as e:
        logger.error(f"Error getting league stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/teams/{team_name}/matches")
async def get_team_matches(team_name: str, limit: int = 10):
    """Get recent matches for a specific team"""
    try:
        matches = storage.get_team_recent_matches(team_name, limit)
        return [
            {
                "id": match.id,
                "league": {
                    "id": match.league.id,
                    "name": match.league.name,
                    "country": match.league.country,
                },
                "home_team": {"id": match.home_team.id, "name": match.home_team.name},
                "away_team": {"id": match.away_team.id, "name": match.away_team.name},
                "home_score": match.home_score,
                "away_score": match.away_score,
                "match_date": match.match_date.isoformat(),
                "season": match.season,
                "status": match.status,
                "minute": match.minute,
                "red_cards_home": match.red_cards_home,
                "red_cards_away": match.red_cards_away,
                "created_at": match.created_at.isoformat(),
                "updated_at": match.updated_at.isoformat(),
            }
            for match in matches
        ]
    except Exception as e:
        logger.error(f"Error getting matches for team {team_name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
