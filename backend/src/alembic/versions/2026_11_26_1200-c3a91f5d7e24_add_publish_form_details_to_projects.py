"""add publish form details to projects

Revision ID: c3a91f5d7e24
Revises: bdcdc189e5c4
Create Date: 2026-11-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'c3a91f5d7e24'
down_revision: Union[str, Sequence[str], None] = 'bdcdc189e5c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('projects', sa.Column('app_type', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('projects', sa.Column('app_description', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('projects', sa.Column('publish_reason', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('projects', 'publish_reason')
    op.drop_column('projects', 'app_description')
    op.drop_column('projects', 'app_type')
