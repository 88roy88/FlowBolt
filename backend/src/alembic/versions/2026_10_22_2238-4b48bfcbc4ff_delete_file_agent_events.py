"""delete file agent events

Revision ID: 4b48bfcbc4ff
Revises: f7b4e12871c0
Create Date: 2026-10-22 22:38:16.458072

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '4b48bfcbc4ff'
down_revision: Union[str, Sequence[str], None] = 'f7b4e12871c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 'file' events are live-only now; history replay never needed them.
    op.execute("DELETE FROM agent_events WHERE event_type = 'file'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
