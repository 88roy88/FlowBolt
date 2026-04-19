"""Optimize publishing: repurpose published_url and add published_at

Revision ID: d3738aeb824c
Revises: 9d6eeadce019
Create Date: 2026-04-19 00:15:02.260384

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'd3738aeb824c'
down_revision: Union[str, Sequence[str], None] = '9d6eeadce019'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Convert empty strings to NULL to satisfy UNIQUE constraint for unpublished projects
    op.execute("UPDATE projects SET published_url = NULL WHERE published_url = ''")

    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('published_at', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.alter_column('published_url',
               existing_type=sa.VARCHAR(),
               nullable=True)
        batch_op.create_unique_constraint(batch_op.f('projects_published_url_key'), ['published_url'])
        # Drop the old slug column if it exists (cleaning up from a previous attempt)
        # Note: drop_column in batch mode handles the constraint removal automatically in SQLite
        batch_op.drop_column('published_slug')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('published_slug', sa.VARCHAR(), autoincrement=False, nullable=True))
        batch_op.drop_constraint(batch_op.f('projects_published_url_key'), type_='unique')
        batch_op.alter_column('published_url',
               existing_type=sa.VARCHAR(),
               nullable=False,
               server_default='')
        batch_op.drop_column('published_at')
    
    op.execute("UPDATE projects SET published_url = '' WHERE published_url IS NULL")
    op.create_unique_constraint('projects_published_slug_key', 'projects', ['published_slug'])
    # ### end Alembic commands ###
