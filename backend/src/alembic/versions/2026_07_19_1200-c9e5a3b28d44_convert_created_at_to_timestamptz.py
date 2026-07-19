"""convert created_at to timestamptz for the group tables

Revision ID: c9e5a3b28d44
Revises: b8d4f2a19c33
Create Date: 2026-07-19 12:00:00.000000

The group tables added on this branch (project_member_groups,
platform_user_groups) stored ``created_at`` as an ISO-8601 string (VARCHAR),
because their SQLModel field was annotated ``str``. This converts each to a real
``timestamptz`` with a ``now()`` server default, mirroring the earlier
agent_events conversion (f550c1c17fde). Existing string values are cast via
``created_at::timestamptz``.

The pre-existing platform_users and project_members tables (created by the RBAC
work, not this branch) are intentionally left as VARCHAR — we don't convert
columns this branch didn't introduce.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9e5a3b28d44'
down_revision: Union[str, Sequence[str], None] = 'b8d4f2a19c33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLES = (
    'project_member_groups',
    'platform_user_groups',
)


def upgrade() -> None:
    """Upgrade schema."""
    for table in _TABLES:
        op.alter_column(
            table, 'created_at',
            existing_type=sa.VARCHAR(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            server_default=sa.func.now(),
            postgresql_using='created_at::timestamptz',
        )


def downgrade() -> None:
    """Downgrade schema."""
    for table in _TABLES:
        op.alter_column(
            table, 'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.VARCHAR(),
            existing_nullable=False,
            server_default=None,
            postgresql_using='created_at::text',
        )
