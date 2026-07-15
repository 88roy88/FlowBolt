"""add project_member_groups table (and merge the two existing heads)

Revision ID: a7c3e9f10b21
Revises: f550c1c17fde, a1b2c3d4e5f6
Create Date: 2026-07-09 10:00:00.000000

The migration history had two divergent heads (both already applied to the DB):
``f550c1c17fde`` (heartbeat/agent-events) and ``a1b2c3d4e5f6`` (rename
followup_diffs). This revision depends on both, merging them back into a single
head, and adds the ``project_member_groups`` table used to grant directory
groups access to a project.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'a7c3e9f10b21'
down_revision: Union[str, Sequence[str], None] = ('f550c1c17fde', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('project_member_groups',
    sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('project_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('group_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('group_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('role', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('created_at', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('invited_by', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('project_id', 'group_id', name='uq_project_member_group')
    )
    op.create_index(op.f('ix_project_member_groups_project_id'), 'project_member_groups', ['project_id'], unique=False)
    op.create_index(op.f('ix_project_member_groups_group_id'), 'project_member_groups', ['group_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_project_member_groups_group_id'), table_name='project_member_groups')
    op.drop_index(op.f('ix_project_member_groups_project_id'), table_name='project_member_groups')
    op.drop_table('project_member_groups')
