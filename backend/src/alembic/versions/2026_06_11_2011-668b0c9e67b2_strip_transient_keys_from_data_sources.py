"""strip_transient_keys_from_data_sources

Revision ID: 668b0c9e67b2
Revises: 812836104eba
Create Date: 2026-06-11 20:11:25.348921

"""

import json
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "668b0c9e67b2"
down_revision: Union[str, Sequence[str], None] = "812836104eba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TRANSIENT_KEYS = {"sample_data", "generated_files"}


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, data_sources FROM projects")).fetchall()
    for project_id, raw in rows:
        if not raw:
            continue
        data_sources = json.loads(raw) if isinstance(raw, str) else raw
        if not data_sources:
            continue
        cleaned = [{k: v for k, v in ds.items() if k not in _TRANSIENT_KEYS} for ds in data_sources]
        conn.execute(
            sa.text("UPDATE projects SET data_sources = :ds WHERE id = :id"),
            {"ds": json.dumps(cleaned), "id": project_id},
        )


def downgrade() -> None:
    pass  # transient fields are gone; cannot restore
