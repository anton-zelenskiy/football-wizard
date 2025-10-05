from pydantic import BaseModel, Field
import structlog

from app.db.models import (
    db,
)


logger = structlog.get_logger()


class LeagueData(BaseModel):
    """League data model for saving league information"""

    league_name: str = Field(description='Name of the league')
    country_name: str = Field(description='Name of the country')


def normalize_country_name(country: str) -> str:
    """Normalize country name to prevent duplicates from different case"""
    if not country:
        return country

    # Convert to title case (first letter uppercase, rest lowercase)
    return country.title()


class FootballDataStorage:
    def __init__(self) -> None:
        self.db = db
