"""add platform_user_groups table

Revision ID: b8d4f2a19c33
Revises: a7c3e9f10b21
Create Date: 2026-07-12 12:00:00.000000

Grants platform access to a whole directory group (mirrors the individual
``platform_users`` allowlist). A user is a platform user if they are directly
listed OR are a member of any group recorded here.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'b8d4f2a19c33'
down_revision: Union[str, Sequence[str], None] = 'a7c3e9f10b21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('platform_user_groups',
    sa.Column('group_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('group_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('invited_by', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('created_at', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.PrimaryKeyConstraint('group_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('platform_user_groups')
