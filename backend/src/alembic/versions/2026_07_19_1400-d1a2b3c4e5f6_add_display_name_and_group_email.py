"""add display_name to users and email to group grants

Revision ID: d1a2b3c4e5f6
Revises: c9e5a3b28d44
Create Date: 2026-07-19 14:00:00.000000

Directory entities carry an ADAPI ``displayName`` and ``mail``. We capture them
at invite time so the sharing/admin UIs can render a two-line row (display name
as the primary text, email underneath) for already-granted principals — the
same shape the live directory search already shows.

- ``project_members.display_name`` / ``platform_users.display_name``: the user's
  displayName (the email already lives in ``user_id``).
- ``project_member_groups.email`` / ``platform_user_groups.email``: the group's
  mail (the displayName already lives in ``group_name``).

All are display-only, backfilled to '' for existing rows, and may go stale — the
access decision always keys on the id (email / DN), never these.

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd1a2b3c4e5f6'
down_revision: Union[str, Sequence[str], None] = 'c9e5a3b28d44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'project_members',
        sa.Column('display_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''),
    )
    op.add_column(
        'platform_users',
        sa.Column('display_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''),
    )
    op.add_column(
        'project_member_groups',
        sa.Column('email', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''),
    )
    op.add_column(
        'platform_user_groups',
        sa.Column('email', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('platform_user_groups', 'email')
    op.drop_column('project_member_groups', 'email')
    op.drop_column('platform_users', 'display_name')
    op.drop_column('project_members', 'display_name')
