from datetime import datetime
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.db.sqlalchemy_models import TeamStanding

from .base_repository import BaseRepository


logger = structlog.get_logger()


class TeamStandingRepository(BaseRepository[TeamStanding]):
    """Repository for TeamStanding operations using async SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, TeamStanding)

    async def get_by_team_league_season(
        self, team_id: int, league_id: int, season: int
    ) -> TeamStanding | None:
        """Fetch a team standing by team_id, league_id, and season."""
        result = await self.session.execute(
            select(TeamStanding).where(
                and_(
                    TeamStanding.team_id == team_id,
                    TeamStanding.league_id == league_id,
                    TeamStanding.season == season,
                )
            )
        )
        return result.scalar_one_or_none()

    async def save_standing(
        self,
        team_id: int,
        league_id: int,
        season: int,
        team_data: dict[str, Any],
    ) -> TeamStanding:
        """Create or update team standing for a specific season.

        Args:
            team_id: ID of the team
            league_id: ID of the league
            season: Season year (e.g., 2024)
            team_data: Dictionary containing standing data with keys:
                - rank: int | None
                - all: dict with 'played', 'win', 'draw', 'lose', 'goals' (with 'for' and 'against')
                - points: int

        Returns:
            TeamStanding instance (created or updated)
        """
        existing = await self.get_by_team_league_season(team_id, league_id, season)

        if existing:
            # Update existing standing
            existing.rank = team_data.get('rank')
            existing.games_played = team_data.get('all', {}).get('played', 0)
            existing.wins = team_data.get('all', {}).get('win', 0)
            existing.draws = team_data.get('all', {}).get('draw', 0)
            existing.losses = team_data.get('all', {}).get('lose', 0)
            existing.goals_scored = (
                team_data.get('all', {}).get('goals', {}).get('for', 0)
            )
            existing.goals_conceded = (
                team_data.get('all', {}).get('goals', {}).get('against', 0)
            )
            existing.points = team_data.get('points', 0)
            existing.updated_at = datetime.now()

            await self.session.commit()
            await self.session.refresh(existing)
            logger.debug(
                f'Updated team standing: team_id={team_id}, league_id={league_id}, season={season}'
            )
            return existing
        else:
            # Create new standing
            new_standing = TeamStanding(
                team_id=team_id,
                league_id=league_id,
                season=season,
                rank=team_data.get('rank'),
                games_played=team_data.get('all', {}).get('played', 0),
                wins=team_data.get('all', {}).get('win', 0),
                draws=team_data.get('all', {}).get('draw', 0),
                losses=team_data.get('all', {}).get('lose', 0),
                goals_scored=team_data.get('all', {}).get('goals', {}).get('for', 0),
                goals_conceded=(
                    team_data.get('all', {}).get('goals', {}).get('against', 0)
                ),
                points=team_data.get('points', 0),
            )
            self.session.add(new_standing)
            await self.session.commit()
            await self.session.refresh(new_standing)
            logger.info(
                f'Created new team standing: team_id={team_id}, league_id={league_id}, season={season}'
            )
            return new_standing

    async def get_standings_by_league_season(
        self, league_id: int, season: int
    ) -> list[TeamStanding]:
        """Get all standings for a league in a specific season."""
        result = await self.session.execute(
            select(TeamStanding).where(
                and_(
                    TeamStanding.league_id == league_id,
                    TeamStanding.season == season,
                )
            )
        )
        return list(result.scalars().all())
