"""migrate_team_data_to_team_standing

Revision ID: 1318a9e85f9d
Revises: 666a2b250cb9
Create Date: 2025-12-03 13:11:38.790107

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Default season for migrated data
DEFAULT_SEASON = 2025


# revision identifiers, used by Alembic.
revision: str = '1318a9e85f9d'
down_revision: Union[str, None] = '666a2b250cb9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Migrate existing Team statistics to TeamStanding table.

    Migrates all teams that have statistics (rank, games_played, points, etc.)
    to TeamStanding table using DEFAULT_SEASON (2025).
    Only migrates teams with actual data (not just default zeros).
    """
    # Migrate teams that have actual statistics
    # Only migrate if team has rank OR has played games OR has points
    op.execute(f"""
        INSERT INTO team_standing (
            team_id,
            league_id,
            season,
            rank,
            games_played,
            wins,
            draws,
            losses,
            goals_scored,
            goals_conceded,
            points,
            created_at,
            updated_at
        )
        SELECT
            id as team_id,
            league_id,
            {DEFAULT_SEASON} as season,
            rank,
            games_played,
            wins,
            draws,
            losses,
            goals_scored,
            goals_conceded,
            points,
            created_at,
            updated_at
        FROM team
        WHERE
            rank IS NOT NULL
            OR games_played > 0
            OR points > 0
            OR wins > 0
            OR draws > 0
            OR losses > 0
            OR goals_scored > 0
            OR goals_conceded > 0
    """)


def downgrade() -> None:
    """Remove migrated TeamStanding data for DEFAULT_SEASON."""
    op.execute(f"""
        DELETE FROM team_standing
        WHERE season = {DEFAULT_SEASON}
    """)
