"""add abort_requested to agent_run_heartbeat

Revision ID: 3b8d5e1f9a27
Revises: 7f3e2a9c1b4d
Create Date: 2026-11-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3b8d5e1f9a27'
down_revision: Union[str, Sequence[str], None] = '7f3e2a9c1b4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'agent_run_heartbeat',
        sa.Column('abort_requested', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('agent_run_heartbeat', 'abort_requested')
