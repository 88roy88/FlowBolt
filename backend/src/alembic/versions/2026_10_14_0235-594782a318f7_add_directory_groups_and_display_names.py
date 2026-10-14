"""add directory groups and display names

Revision ID: 594782a318f7
Revises: c68747447b66
Create Date: 2026-10-14 02:35:35.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '594782a318f7'
down_revision: Union[str, Sequence[str], None] = 'c68747447b66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_USER_TABLES = ('platform_users', 'project_members')


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('project_member_groups',
    sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('project_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('group_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('group_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('email', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''),
    sa.Column('role', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Column('invited_by', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('project_id', 'group_id', name='uq_project_member_group')
    )
    op.create_index(op.f('ix_project_member_groups_project_id'), 'project_member_groups', ['project_id'], unique=False)
    op.create_index(op.f('ix_project_member_groups_group_id'), 'project_member_groups', ['group_id'], unique=False)

    op.create_table('platform_user_groups',
    sa.Column('group_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('group_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('email', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''),
    sa.Column('invited_by', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.PrimaryKeyConstraint('group_id')
    )

    for table in _USER_TABLES:
        op.alter_column(
            table, 'created_at',
            existing_type=sa.VARCHAR(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            server_default=sa.func.now(),
            postgresql_using='created_at::timestamptz',
        )
        op.add_column(
            table,
            sa.Column('display_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''),
        )


def downgrade() -> None:
    """Downgrade schema."""
    for table in _USER_TABLES:
        op.drop_column(table, 'display_name')
        op.alter_column(
            table, 'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.VARCHAR(),
            existing_nullable=False,
            server_default=None,
            postgresql_using='created_at::text',
        )

    op.drop_table('platform_user_groups')

    op.drop_index(op.f('ix_project_member_groups_group_id'), table_name='project_member_groups')
    op.drop_index(op.f('ix_project_member_groups_project_id'), table_name='project_member_groups')
    op.drop_table('project_member_groups')
