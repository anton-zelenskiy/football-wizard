from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.db.sqlalchemy_models import League, Match, Team
from app.scraper.livesport_scraper import CommonMatchData

from .base_repository import BaseRepository


logger = structlog.get_logger()


def normalize_country_name(country: str) -> str:
    """Normalize country name to prevent duplicates from different case"""
    if not country:
        return country
    # Convert to title case (first letter uppercase, rest lowercase)
    return country.title()


class MatchRepository(BaseRepository[Match]):
    """Repository for Match operations using async SQLAlchemy"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Match)

    async def save_match(self, match_data: 'CommonMatchData') -> Match:
        """Unified method to save any type of match (live, finished, scheduled)"""
        try:
            # Normalize country name to prevent duplicates
            normalized_country = normalize_country_name(match_data.country)

            # Find or create league
            league_result = await self.session.execute(
                select(League).where(
                    and_(
                        League.name == match_data.league,
                        League.country == normalized_country,
                    )
                )
            )
            league = league_result.scalar_one_or_none()

            if not league:
                league = League(name=match_data.league, country=normalized_country)
                self.session.add(league)
                await self.session.commit()
                await self.session.refresh(league)
                logger.info(f'Created new league: {league.name}')

            # Find or create teams
            home_team_result = await self.session.execute(
                select(Team).where(
                    and_(Team.name == match_data.home_team, Team.league_id == league.id)
                )
            )
            home_team = home_team_result.scalar_one_or_none()

            if not home_team:
                home_team = Team(name=match_data.home_team, league_id=league.id)
                self.session.add(home_team)
                await self.session.commit()
                await self.session.refresh(home_team)
                logger.info(f'Created new home team: {home_team.name}')

            away_team_result = await self.session.execute(
                select(Team).where(
                    and_(Team.name == match_data.away_team, Team.league_id == league.id)
                )
            )
            away_team = away_team_result.scalar_one_or_none()

            if not away_team:
                away_team = Team(name=match_data.away_team, league_id=league.id)
                self.session.add(away_team)
                await self.session.commit()
                await self.session.refresh(away_team)
                logger.info(f'Created new away team: {away_team.name}')

            # Use season from match data (parsed from page)
            season = match_data.season
            round_number = match_data.round_number

            # Check if match already exists using core identifying fields
            existing_match_result = await self.session.execute(
                select(Match).where(
                    and_(
                        Match.league_id == league.id,
                        Match.home_team_id == home_team.id,
                        Match.away_team_id == away_team.id,
                        Match.season == season,
                    )
                )
            )
            existing_match = existing_match_result.scalar_one_or_none()

            if existing_match:
                # Update existing match
                await self.update_match_status(
                    existing_match.id,
                    match_data.status,
                    home_score=match_data.home_score,
                    away_score=match_data.away_score,
                    minute=match_data.minute,
                    red_cards_home=match_data.red_cards_home,
                    red_cards_away=match_data.red_cards_away,
                )
                logger.info(
                    f'Updated existing match: {home_team.name} vs {away_team.name} ({match_data.status})'
                )
                return existing_match
            else:
                # Create new match
                new_match = Match(
                    league_id=league.id,
                    home_team_id=home_team.id,
                    away_team_id=away_team.id,
                    home_score=match_data.home_score,
                    away_score=match_data.away_score,
                    match_date=match_data.match_date or datetime.now(),
                    season=season,
                    round=round_number,
                    status=match_data.status,
                    minute=match_data.minute,
                    red_cards_home=match_data.red_cards_home,
                    red_cards_away=match_data.red_cards_away,
                )
                self.session.add(new_match)
                await self.session.commit()
                await self.session.refresh(new_match)
                logger.info(
                    f'Created new match: {home_team.name} vs {away_team.name} ({match_data.status})'
                )
                return new_match

        except Exception as e:
            await self.session.rollback()
            logger.error(f'Error saving match: {e}')
            raise

    async def update_match_status(
        self, match_id: int, new_status: str, **kwargs: Any
    ) -> Match | None:
        """Update match status and related fields, handling lifecycle transitions"""
        try:
            match = await self.get_by_id(match_id)
            if not match:
                logger.warning(f'Match {match_id} not found for status update')
                return None

            old_status = match.status
            match.status = new_status
            match.updated_at = datetime.now()

            # Handle status-specific field updates
            if new_status == 'live':
                # Set live-specific fields
                match.minute = kwargs.get('minute')
                match.red_cards_home = kwargs.get('red_cards_home', 0)
                match.red_cards_away = kwargs.get('red_cards_away', 0)
                if 'home_score' in kwargs:
                    match.home_score = kwargs['home_score']
                if 'away_score' in kwargs:
                    match.away_score = kwargs['away_score']

            elif new_status == 'finished':
                # Clear live-specific fields when match finishes (set to defaults)
                match.minute = None
                match.red_cards_home = 0  # Set to default value, not None
                match.red_cards_away = 0  # Set to default value, not None
                # Ensure final scores are set
                if 'home_score' in kwargs:
                    match.home_score = kwargs['home_score']
                if 'away_score' in kwargs:
                    match.away_score = kwargs['away_score']

            elif new_status == 'scheduled':
                # Clear live/finished specific fields (set to defaults)
                match.minute = None
                match.red_cards_home = 0  # Set to default value, not None
                match.red_cards_away = 0  # Set to default value, not None
                match.home_score = None
                match.away_score = None

            await self.session.commit()
            await self.session.refresh(match)
            logger.info(
                f'Updated match status: {match_id} {old_status} -> {new_status}'
            )
            return match

        except Exception as e:
            await self.session.rollback()
            logger.error(f'Error updating match {match_id} status: {e}')
            raise

    async def get_matches_by_status(self, status: str) -> list[Match]:
        """Get matches by specific status with relationships loaded"""
        try:
            result = await self.session.execute(
                select(Match)
                .options(
                    selectinload(Match.home_team),
                    selectinload(Match.away_team),
                    selectinload(Match.league),
                )
                .where(Match.status == status)
                .order_by(Match.match_date.asc())
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f'Error getting matches by status {status}: {e}')
            return []

    async def get_team_matches_by_season_and_rounds(
        self,
        team_id: int,
        season: int,
        before_date: datetime | None = None,
        limit: int = 5,
    ) -> list[Match]:
        """Get team's most recent matches from specific season for analysis.

        Gets the N most recent finished matches (by match_date) for a team in a season,
        optionally before a specific date. This handles cases where matches from higher
        rounds may be played earlier.

        Args:
            team_id: Team ID
            season: Season year
            before_date: Optional date to get matches before (exclusive). If None,
                        gets the latest match_date for the team and uses that.
            limit: Number of matches to return (default: 5)

        Returns:
            List of matches ordered by match_date descending (most recent first)
        """
        try:
            # If before_date is not provided, get the latest match_date for this team
            if before_date is None:
                latest_date_result = await self.session.execute(
                    select(func.max(Match.match_date)).where(
                        and_(
                            (Match.home_team_id == team_id)
                            | (Match.away_team_id == team_id),
                            Match.season == season,
                            Match.status == 'finished',
                        )
                    )
                )
                before_date = latest_date_result.scalar_one_or_none()

            if before_date is None:
                logger.debug(
                    f'No finished matches found for team {team_id} in season {season}'
                )
                return []

            # Get matches where team participated before the specified date
            result = await self.session.execute(
                select(Match)
                .options(
                    selectinload(Match.home_team),
                    selectinload(Match.away_team),
                    selectinload(Match.league),
                )
                .where(
                    and_(
                        (Match.home_team_id == team_id)
                        | (Match.away_team_id == team_id),
                        Match.season == season,
                        Match.match_date < before_date,
                        Match.status == 'finished',
                    )
                )
                .order_by(Match.match_date.desc())
                .limit(limit)
            )

            match_list = list(result.scalars().all())
            logger.debug(
                f'Found {len(match_list)} matches for team {team_id} before {before_date}'
            )
            return match_list
        except Exception as e:
            logger.error(
                'Error getting matches',
                error=str(e),
                before_date=before_date,
                limit=limit,
                team_id=team_id,
                season=season,
            )
            return []

    async def get_matches_by_league_season_round(
        self, league_id: int, season: int, round_number: int
    ) -> list[Match]:
        """Get matches by league, season, and round number"""
        try:
            result = await self.session.execute(
                select(Match)
                .options(
                    selectinload(Match.home_team),
                    selectinload(Match.away_team),
                    selectinload(Match.league).selectinload(League.teams),
                )
                .where(
                    and_(
                        Match.league_id == league_id,
                        Match.season == season,
                        Match.round == round_number,
                        Match.status == 'finished',
                    )
                )
                .order_by(Match.match_date.asc())
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(
                f'Error getting matches by league/season/round: {e}',
                league_id=league_id,
                season=season,
                round_number=round_number,
            )
            return []

    async def get_max_round_by_league_season(
        self, league_id: int, season: int
    ) -> int | None:
        """Get maximum round number for a league and season"""
        try:
            result = await self.session.execute(
                select(func.max(Match.round)).where(
                    and_(
                        Match.league_id == league_id,
                        Match.season == season,
                        Match.status == 'finished',
                    )
                )
            )
            max_round = result.scalar_one_or_none()
            return max_round if max_round is not None else None
        except Exception as e:
            logger.error(
                f'Error getting max round: {e}',
                league_id=league_id,
                season=season,
            )
            return None

    async def get_league_by_name_and_country(
        self, league_name: str, country_name: str
    ) -> League | None:
        """Get league by name and country"""
        try:
            normalized_country = normalize_country_name(country_name)
            result = await self.session.execute(
                select(League).where(
                    and_(
                        League.name == league_name,
                        League.country == normalized_country,
                    )
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(
                f'Error getting league: {e}',
                league_name=league_name,
                country=country_name,
            )
            return None
