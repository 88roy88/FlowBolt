"""add last_trace_id to projects

Revision ID: 3b9d5e7a2c61
Revises: 7f3e2a9c1b4d
Create Date: 2026-10-28 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3b9d5e7a2c61'
down_revision: Union[str, Sequence[str], None] = '7f3e2a9c1b4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('projects', sa.Column('last_trace_id', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('projects', 'last_trace_id')
