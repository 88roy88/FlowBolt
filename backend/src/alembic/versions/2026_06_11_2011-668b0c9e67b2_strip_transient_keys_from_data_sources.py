"""strip_transient_keys_from_data_sources

Revision ID: 668b0c9e67b2
Revises: 812836104eba
Create Date: 2026-06-11 20:11:25.348921

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "668b0c9e67b2"
down_revision: Union[str, Sequence[str], None] = "812836104eba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text("""
        UPDATE projects
        SET data_sources = (
            SELECT json_agg(elem::jsonb - 'sample_data' - 'generated_files')
            FROM json_array_elements(data_sources) AS elem
        )
        WHERE data_sources IS NOT NULL
          AND data_sources::text NOT IN ('null', '[]')
    """)
    )


def downgrade() -> None:
    pass  # transient fields are gone; cannot restore
