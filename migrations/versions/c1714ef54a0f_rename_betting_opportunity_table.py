"""rename_betting_opportunity_table

Revision ID: c1714ef54a0f
Revises: 2d9c54b64bcb
Create Date: 2025-12-03 13:33:22.065785

Renames BettingOpportunity table to betting_opportunity for consistency with other table names.
Also updates the foreign key reference in notificationlog table.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1714ef54a0f'
down_revision: Union[str, None] = '2d9c54b64bcb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename BettingOpportunity table to betting_opportunity and update foreign key."""
    # SQLite doesn't support renaming tables directly with ALTER TABLE RENAME in Alembic
    # So we need to use op.rename_table() which handles it properly
    op.rename_table('BettingOpportunity', 'betting_opportunity')

    # Update the foreign key constraint in notificationlog table
    # SQLite requires recreating the table to change foreign key references
    # First, create a new notificationlog table with updated foreign key
    op.create_table(
        'notificationlog_new',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('opportunity_id', sa.Integer(), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['opportunity_id'], ['betting_opportunity.id']),
        sa.ForeignKeyConstraint(['user_id'], ['telegramuser.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Copy data from old table to new table
    op.execute("""
        INSERT INTO notificationlog_new
        SELECT * FROM notificationlog
    """)

    # Drop old table
    op.drop_table('notificationlog')

    # Rename new table to original name
    op.rename_table('notificationlog_new', 'notificationlog')


def downgrade() -> None:
    """Rename betting_opportunity table back to BettingOpportunity and update foreign key."""
    # Rename table back
    op.rename_table('betting_opportunity', 'BettingOpportunity')

    # Recreate notificationlog table with old foreign key reference
    op.create_table(
        'notificationlog_new',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('opportunity_id', sa.Integer(), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['opportunity_id'], ['BettingOpportunity.id']),
        sa.ForeignKeyConstraint(['user_id'], ['telegramuser.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Copy data
    op.execute("""
        INSERT INTO notificationlog_new
        SELECT * FROM notificationlog
    """)

    # Drop old table
    op.drop_table('notificationlog')

    # Rename new table
    op.rename_table('notificationlog_new', 'notificationlog')
