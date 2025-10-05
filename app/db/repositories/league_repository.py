from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.db.sqlalchemy_models import League

from .base_repository import BaseRepository


logger = structlog.get_logger()


def normalize_country_name(country: str) -> str:
    """Normalize country name to prevent duplicates from different case."""
    if not country:
        return country
    return country.title()


class LeagueRepository(BaseRepository[League]):
    """Repository for League operations using async SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, League)

    async def get_by_name_and_country(
        self, league_name: str, country_name: str
    ) -> League | None:
        """Fetch a league by name and country (case-normalized)."""
        normalized_country = normalize_country_name(country_name)
        result = await self.session.execute(
            select(League).where(
                and_(League.name == league_name, League.country == normalized_country)
            )
        )
        return result.scalar_one_or_none()

    async def save_league(self, league_name: str, country_name: str) -> League:
        """Create league if not exists, otherwise return existing one.

        Mirrors the semantics of Peewee-based save in storage.
        """
        normalized_country = normalize_country_name(country_name)

        existing = await self.get_by_name_and_country(league_name, normalized_country)
        if existing:
            logger.debug(f'League already exists: {league_name} - {normalized_country}')
            return existing

        league = League(name=league_name, country=normalized_country)
        self.session.add(league)
        await self.session.commit()
        await self.session.refresh(league)
        logger.info('Created new league', name=league.name, country=league.country)
        return league

    async def get_or_create(self, league_name: str, country_name: str) -> League:
        """Alias for save_league for clarity with get-or-create semantics."""
        return await self.save_league(league_name, country_name)
