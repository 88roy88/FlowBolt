"""delete stored 'file' agent events (now live-only)

Revision ID: 7f3e9a1c2b4d
Revises: 594782a318f7
Create Date: 2026-10-22 22:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "7f3e9a1c2b4d"
down_revision: Union[str, Sequence[str], None] = "594782a318f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM agent_events WHERE event_type = 'file'")


def downgrade() -> None:
    # Deleted events are gone; history replay never needed them.
    pass
