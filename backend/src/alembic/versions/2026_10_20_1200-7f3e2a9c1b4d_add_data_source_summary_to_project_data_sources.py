"""add data_source_summary to project_data_sources

Revision ID: 7f3e2a9c1b4d
Revises: 594782a318f7
Create Date: 2026-10-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f3e2a9c1b4d'
down_revision: Union[str, Sequence[str], None] = '594782a318f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'project_data_sources',
        sa.Column('data_source_summary', sa.String(), nullable=False, server_default=''),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('project_data_sources', 'data_source_summary')
