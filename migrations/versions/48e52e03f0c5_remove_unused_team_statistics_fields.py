"""remove_unused_team_statistics_fields

Revision ID: 48e52e03f0c5
Revises: c1714ef54a0f
Create Date: 2025-12-03 13:55:47.151670

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '48e52e03f0c5'
down_revision: Union[str, None] = 'c1714ef54a0f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove unused statistics fields from Team table.

    Removes: rank, games_played, wins, draws, losses, goals_scored, goals_conceded, points
    These fields are now stored in TeamStanding model for season-specific data.
    """
    # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
    # Create new table without the statistics columns
    op.create_table(
        'team_new',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('league_id', sa.Integer(), nullable=False),
        sa.Column('coach', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['league_id'], ['league.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Copy data from old table to new table (excluding dropped columns)
    op.execute("""
        INSERT INTO team_new (id, name, league_id, coach, created_at, updated_at)
        SELECT id, name, league_id, coach, created_at, updated_at
        FROM team
    """)

    # Drop old table
    op.drop_table('team')

    # Rename new table to original name
    op.rename_table('team_new', 'team')


def downgrade() -> None:
    """Restore statistics fields to Team table."""
    # Create new table with all original columns
    op.create_table(
        'team_new',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('league_id', sa.Integer(), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=True),
        sa.Column('games_played', sa.Integer(), nullable=True),
        sa.Column('wins', sa.Integer(), nullable=True),
        sa.Column('draws', sa.Integer(), nullable=True),
        sa.Column('losses', sa.Integer(), nullable=True),
        sa.Column('goals_scored', sa.Integer(), nullable=True),
        sa.Column('goals_conceded', sa.Integer(), nullable=True),
        sa.Column('points', sa.Integer(), nullable=True),
        sa.Column('coach', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['league_id'], ['league.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Copy data from current table (statistics will be NULL)
    op.execute("""
        INSERT INTO team_new (id, name, league_id, coach, created_at, updated_at,
                             rank, games_played, wins, draws, losses, goals_scored, goals_conceded, points)
        SELECT id, name, league_id, coach, created_at, updated_at,
               NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
        FROM team
    """)

    # Drop current table
    op.drop_table('team')

    # Rename new table to original name
    op.rename_table('team_new', 'team')
