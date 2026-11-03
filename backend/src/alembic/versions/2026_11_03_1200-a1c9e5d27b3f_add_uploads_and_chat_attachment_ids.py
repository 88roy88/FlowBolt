"""add uploads table and chat_messages.attachment_ids

Revision ID: a1c9e5d27b3f
Revises: 7f3e2a9c1b4d
Create Date: 2026-11-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c9e5d27b3f'
down_revision: Union[str, Sequence[str], None] = '7f3e2a9c1b4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'uploads',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('kind', sa.Enum('attachment', 'asset', name='uploadkind'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('s3_key', sa.String(), nullable=False),
        sa.Column('content_type', sa.String(), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.Column('deleted_at', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_uploads_project_id'), 'uploads', ['project_id'], unique=False)
    op.add_column('chat_messages', sa.Column('attachment_ids', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('chat_messages', 'attachment_ids')
    op.drop_index(op.f('ix_uploads_project_id'), table_name='uploads')
    op.drop_table('uploads')
    sa.Enum(name='uploadkind').drop(op.get_bind(), checkfirst=True)
