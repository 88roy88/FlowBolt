"""add (project_id, event_type, id) index to agent_events

Revision ID: 8a4b2c6d1e3f
Revises: 7f3e9a1c2b4d
Create Date: 2026-10-22 22:10:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "8a4b2c6d1e3f"
down_revision: Union[str, Sequence[str], None] = "7f3e9a1c2b4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_agent_events_project_id_event_type_id", "agent_events", ["project_id", "event_type", "id"])


def downgrade() -> None:
    op.drop_index("ix_agent_events_project_id_event_type_id", table_name="agent_events")
