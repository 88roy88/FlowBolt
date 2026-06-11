"""drop legacy single data source columns

Revision ID: 812836104eba
Revises: bf979c9b9417
Create Date: 2026-06-11 15:41:50.241671

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '812836104eba'
down_revision: Union[str, Sequence[str], None] = 'bf979c9b9417'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('projects', 'data_source_context')
    op.drop_column('projects', 'data_source_id')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('projects', sa.Column('data_source_id', sqlmodel.sql.sqltypes.AutoString(),
               nullable=False, server_default=''))
    op.add_column('projects', sa.Column('data_source_context', sqlmodel.sql.sqltypes.AutoString(),
               nullable=False, server_default=''))
