"""remove_r_oviedo_team

Revision ID: 2d9c54b64bcb
Revises: 1318a9e85f9d
Create Date: 2025-12-03 13:25:17.943798

Removes the duplicate "R. Oviedo" team (old team with wrong stats) from the database.
The correct team is "Oviedo". This migration removes all references to "R. Oviedo" and
then deletes the team itself.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2d9c54b64bcb'
down_revision: Union[str, None] = '1318a9e85f9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove R. Oviedo team and all its references.

    Deletion order (due to foreign key constraints):
    1. Delete BettingOpportunity records referencing R. Oviedo matches
    2. Delete Match records with R. Oviedo as home_team or away_team
    3. Delete TeamStanding records for R. Oviedo
    4. Delete Team record for R. Oviedo
    """
    # Get the team ID for R. Oviedo
    connection = op.get_bind()
    result = connection.execute(
        sa.text("SELECT id FROM team WHERE name = 'R. Oviedo'")
    )
    team_row = result.fetchone()

    if not team_row:
        print("Team 'R. Oviedo' not found, skipping deletion")
        return

    team_id = team_row[0]
    print(f"Found R. Oviedo team with ID: {team_id}")

    # 1. Delete BettingOpportunity records that reference matches with R. Oviedo
    op.execute(f"""
        DELETE FROM betting_opportunity
        WHERE match_id IN (
            SELECT id FROM match
            WHERE home_team_id = {team_id} OR away_team_id = {team_id}
        )
    """)
    print("Deleted BettingOpportunity records referencing R. Oviedo matches")

    # 2. Delete Match records with R. Oviedo as home_team or away_team
    op.execute(f"""
        DELETE FROM match
        WHERE home_team_id = {team_id} OR away_team_id = {team_id}
    """)
    print("Deleted Match records with R. Oviedo")

    # 3. Delete TeamStanding records for R. Oviedo
    op.execute(f"""
        DELETE FROM team_standing
        WHERE team_id = {team_id}
    """)
    print("Deleted TeamStanding records for R. Oviedo")

    # 4. Delete Team record for R. Oviedo
    op.execute(f"""
        DELETE FROM team
        WHERE id = {team_id}
    """)
    print(f"Deleted Team record for R. Oviedo (ID: {team_id})")


def downgrade() -> None:
    """Cannot restore deleted data - this migration is irreversible."""
    print("Warning: Cannot restore deleted R. Oviedo team and its references.")
    print("This migration is irreversible.")
