"""Utility functions for betting rules analysis."""

import structlog

from app.bet_rules.bet_rules import Bet
from app.bet_rules.rule_engine import BettingRulesEngine
from app.bet_rules.structures import MatchSummary
from app.db.repositories.match_repository import MatchRepository
from app.db.repositories.team_standing_repository import TeamStandingRepository
from app.db.session import get_async_db_session


logger = structlog.get_logger()


async def analyze_match_by_id(match_id: int, rounds_back: int = 5) -> list[Bet] | None:
    """Analyze a specific match by ID and return betting opportunities.

    Args:
        match_id: The ID of the match to analyze
        rounds_back: Number of previous rounds to use for analysis (default: 5)

    Returns:
        List of betting opportunities (Bet objects) if match found, None otherwise
    """
    logger.info('Analyzing match by ID', match_id=match_id, rounds_back=rounds_back)

    async with get_async_db_session() as session:
        match_repo = MatchRepository(session)
        standing_repo = TeamStandingRepository(session)

        # Get match by ID with relationships loaded
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.db.sqlalchemy_models import Match

        result = await session.execute(
            select(Match)
            .options(
                selectinload(Match.home_team),
                selectinload(Match.away_team),
                selectinload(Match.league),
            )
            .where(Match.id == match_id)
        )
        match = result.scalar_one_or_none()

        if not match:
            logger.error(f'Match not found: {match_id}')
            return None

        if not match.season:
            logger.error(f'Match {match_id} has no season information')
            return None

        logger.info(
            f'Found match: {match.home_team.name} vs {match.away_team.name} '
            f'(Season {match.season}, Round {match.round})'
        )

        # Get recent matches for both teams before this match's date
        home_recent_matches = await match_repo.get_team_matches_by_season_and_rounds(
            match.home_team.id,
            match.season,
            before_date=match.match_date,
            limit=rounds_back,
        )
        away_recent_matches = await match_repo.get_team_matches_by_season_and_rounds(
            match.away_team.id,
            match.season,
            before_date=match.match_date,
            limit=rounds_back,
        )

        logger.info(
            f'Recent matches - Home: {len(home_recent_matches)}, Away: {len(away_recent_matches)}'
        )

        # Get team ranks from TeamStanding
        home_rank = None
        away_rank = None
        home_standing = await standing_repo.get_by_team_league_season(
            match.home_team.id, match.league.id, match.season
        )
        away_standing = await standing_repo.get_by_team_league_season(
            match.away_team.id, match.league.id, match.season
        )
        if home_standing:
            home_rank = home_standing.rank
        if away_standing:
            away_rank = away_standing.rank

        logger.info(f'Team ranks - Home: {home_rank}, Away: {away_rank}')

        # Get teams count from TeamStanding for this season
        teams_count_result = await standing_repo.get_standings_by_league_season(
            match.league.id, match.season
        )
        teams_count = len(teams_count_result) if teams_count_result else 0

        # Create MatchSummary
        try:
            match_summary = MatchSummary.from_match(
                match, home_rank, away_rank, teams_count=teams_count
            )
        except Exception as e:
            logger.error(f'Error creating match summary: {e}')
            return None

        # Convert recent matches to Pydantic models
        home_matches_data = [m.to_pydantic() for m in home_recent_matches]
        away_matches_data = [m.to_pydantic() for m in away_recent_matches]

        match_summary.home_recent_matches = home_matches_data
        match_summary.away_recent_matches = away_matches_data

        # Analyze match using rules engine
        rules_engine = BettingRulesEngine()
        opportunities = rules_engine.analyze_match(match_summary)

        logger.info(
            f'Found {len(opportunities)} betting opportunities for match {match_id}'
        )

        return opportunities
