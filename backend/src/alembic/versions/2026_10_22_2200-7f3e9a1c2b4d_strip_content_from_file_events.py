"""strip file content from stored 'file' agent events

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
    op.execute("UPDATE agent_events SET payload = (payload::jsonb - 'content')::json WHERE event_type = 'file'")


def downgrade() -> None:
    # The stripped content is gone; replay never needed it.
    pass
