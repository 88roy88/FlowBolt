"""rename event_type value 'followup_diffs' to 'file_diffs' in agent_events

Revision ID: a1b2c3d4e5f6
Revises: 9252bbb0fae2
Create Date: 2026-06-29 00:01:00.000000

"""

import json
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "9252bbb0fae2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_TYPE = "followup_diffs"
NEW_TYPE = "file_diffs"


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, payload FROM agent_events WHERE event_type = :t"),
        {"t": OLD_TYPE},
    ).fetchall()
    for row_id, raw in rows:
        payload = json.loads(raw) if isinstance(raw, str) else (raw or {})
        payload["type"] = NEW_TYPE
        conn.execute(
            sa.text(
                "UPDATE agent_events SET event_type = :new_t, payload = :payload WHERE id = :id"
            ),
            {"new_t": NEW_TYPE, "payload": json.dumps(payload), "id": row_id},
        )


def downgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, payload FROM agent_events WHERE event_type = :t"),
        {"t": NEW_TYPE},
    ).fetchall()
    for row_id, raw in rows:
        payload = json.loads(raw) if isinstance(raw, str) else (raw or {})
        payload["type"] = OLD_TYPE
        conn.execute(
            sa.text(
                "UPDATE agent_events SET event_type = :old_t, payload = :payload WHERE id = :id"
            ),
            {"old_t": OLD_TYPE, "payload": json.dumps(payload), "id": row_id},
        )
