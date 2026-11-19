"""add feature flags

Revision ID: 3c8d1f6a2e47
Revises: bdcdc189e5c4
Create Date: 2026-11-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '3c8d1f6a2e47'
down_revision: Union[str, Sequence[str], None] = 'bdcdc189e5c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('feature_flags',
    sa.Column('key', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('enabled_for_all', sa.Boolean(), nullable=False),
    sa.Column('enabled_for_admins', sa.Boolean(), nullable=False),
    sa.Column('updated_by', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('feature_flag_targets',
    sa.Column('flag_key', sa.String(), nullable=False),
    sa.Column('target_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('target_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('display_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('email', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('added_by', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['flag_key'], ['feature_flags.key'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('flag_key', 'target_type', 'target_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('feature_flag_targets')
    op.drop_table('feature_flags')
