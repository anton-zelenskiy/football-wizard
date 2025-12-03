from datetime import datetime
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.db.sqlalchemy_models import League, Team
from app.scraper.constants import DEFAULT_SEASON

from .base_repository import BaseRepository
from .team_standing_repository import TeamStandingRepository


logger = structlog.get_logger()


def normalize_country_name(country: str) -> str:
    """Normalize country name to prevent duplicates from different case."""
    if not country:
        return country
    return country.title()


class TeamRepository(BaseRepository[Team]):
    """Repository for Team operations using async SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Team)

    async def get_by_name_and_league(
        self, team_name: str, league_id: int
    ) -> Team | None:
        """Fetch a team by name and league ID."""
        result = await self.session.execute(
            select(Team).where(
                and_(Team.name == team_name, Team.league_id == league_id)
            )
        )
        return result.scalar_one_or_none()

    async def get_league_by_name_and_country(
        self, league_name: str, country_name: str
    ) -> League:
        """Fetch a league by name and country (case-normalized)."""
        normalized_country = normalize_country_name(country_name)
        result = await self.session.execute(
            select(League).where(
                and_(League.name == league_name, League.country == normalized_country)
            )
        )
        return result.scalar_one_or_none()

    async def save_team_standings(
        self,
        team_data: dict[str, Any],
        league_name: str,
        country: str,
        season: int | None = DEFAULT_SEASON,
    ) -> tuple[Team | None, dict[str, Any] | None]:
        """Save team standings/statistics.

        Mirrors the semantics of Peewee-based save_team_standings in storage.
        Also saves to TeamStanding for season-specific tracking.
        Returns tuple of (Team | None, coach_change_info | None).
        coach_change_info contains: team_name, league_name, country, old_coach, new_coach

        Args:
            team_data: Team standing data dictionary
            league_name: Name of the league
            country: Country name
            season: Optional season year (e.g., 2024)
        """

        # Normalize country name to prevent duplicates
        normalized_country = normalize_country_name(country)

        # Find league
        league = await self.get_league_by_name_and_country(
            league_name, normalized_country
        )
        if not league:
            logger.error(f'League not found: {normalized_country} - {league_name}')
            return None, None

        # Extract team name
        team_name = team_data.get('team', {}).get('name', '')
        if not team_name:
            logger.error(f'Team not found: {team_data}')
            return None, None

        # Check if team exists
        existing_team = await self.get_by_name_and_league(team_name, league.id)

        coach_change_info = None

        if existing_team:
            # Check for coach change
            old_coach = existing_team.coach
            new_coach = team_data.get('coach')

            if (
                old_coach != new_coach
                and old_coach is not None
                and new_coach is not None
            ):
                coach_change_info = {
                    'team_name': team_name,
                    'league_name': league_name,
                    'country': normalized_country,
                    'old_coach': old_coach,
                    'new_coach': new_coach,
                }
                logger.info(
                    f'Coach change detected for {team_name}: {old_coach} -> {new_coach}'
                )

            # Update existing team statistics
            existing_team.rank = team_data.get('rank')
            existing_team.games_played = team_data.get('all', {}).get('played', 0)
            existing_team.wins = team_data.get('all', {}).get('win', 0)
            existing_team.draws = team_data.get('all', {}).get('draw', 0)
            existing_team.losses = team_data.get('all', {}).get('lose', 0)
            existing_team.goals_scored = (
                team_data.get('all', {}).get('goals', {}).get('for', 0)
            )
            existing_team.goals_conceded = (
                team_data.get('all', {}).get('goals', {}).get('against', 0)
            )
            existing_team.points = team_data.get('points', 0)
            if 'coach' in team_data:
                existing_team.coach = team_data.get('coach')
            existing_team.updated_at = datetime.now()

            await self.session.commit()
            await self.session.refresh(existing_team)
            logger.debug(f'Updated team statistics: {existing_team.name}')

            # Also save to TeamStanding for season-specific tracking
            standing_repo = TeamStandingRepository(self.session)
            await standing_repo.save_standing(
                existing_team.id, league.id, season, team_data
            )

            return existing_team, coach_change_info
        else:
            # Create new team
            new_team = Team(
                name=team_name,
                league_id=league.id,
                rank=team_data.get('rank'),
                games_played=team_data.get('all', {}).get('played', 0),
                wins=team_data.get('all', {}).get('win', 0),
                draws=team_data.get('all', {}).get('draw', 0),
                losses=team_data.get('all', {}).get('lose', 0),
                goals_scored=team_data.get('all', {}).get('goals', {}).get('for', 0),
                goals_conceded=team_data.get('all', {})
                .get('goals', {})
                .get('against', 0),
                points=team_data.get('points', 0),
                coach=team_data.get('coach'),
            )
            self.session.add(new_team)
            await self.session.commit()
            await self.session.refresh(new_team)
            logger.info(f'Created new team: {new_team.name}')

            # Also save to TeamStanding for season-specific tracking
            standing_repo = TeamStandingRepository(self.session)
            await standing_repo.save_standing(new_team.id, league.id, season, team_data)

            return new_team, None

    async def get_or_create_team(self, team_name: str, league_id: int) -> Team:
        """Get existing team or create new one."""
        existing = await self.get_by_name_and_league(team_name, league_id)
        if existing:
            return existing

        new_team = Team(name=team_name, league_id=league_id)
        self.session.add(new_team)
        await self.session.commit()
        await self.session.refresh(new_team)
        logger.info(f'Created new team: {new_team.name}')
        return new_team
