"""add display_name to platform_users and project_members

Revision ID: e2f6a9c4d871
Revises: c9e5a3b28d44
Create Date: 2026-07-30 14:00:00.000000

Both tables were created by bf979c9b9417, which is already merged, so the
columns have to be added after the fact for databases that are past that
revision.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'e2f6a9c4d871'
down_revision: Union[str, Sequence[str], None] = 'c9e5a3b28d44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLES = ('platform_users', 'project_members')


def upgrade() -> None:
    """Upgrade schema."""
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column('display_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''),
        )


def downgrade() -> None:
    """Downgrade schema."""
    for table in _TABLES:
        op.drop_column(table, 'display_name')
