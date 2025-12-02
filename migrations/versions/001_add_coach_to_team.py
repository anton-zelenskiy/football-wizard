"""add coach to team

Revision ID: 001
Revises:
Create Date: 2025-12-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add coach column to team table
    op.add_column('team', sa.Column('coach', sa.String(), nullable=True))


def downgrade() -> None:
    # Remove coach column from team table
    op.drop_column('team', 'coach')
