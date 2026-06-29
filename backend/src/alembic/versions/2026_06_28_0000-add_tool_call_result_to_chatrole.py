"""Add tool_call and tool_result values to chatrole enum

Revision ID: add_tool_roles_chatrole
Revises: 9252bbb0fae2
Create Date: 2026-06-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'add_tool_roles_chatrole'
down_revision: Union[str, Sequence[str], None] = '9252bbb0fae2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE chatrole ADD VALUE IF NOT EXISTS 'tool_call'")
    op.execute("ALTER TYPE chatrole ADD VALUE IF NOT EXISTS 'tool_result'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values without recreating the type.
    # To downgrade: recreate chatrole without the new values and cast the column.
    op.execute("""
        DELETE FROM chat_messages WHERE role IN ('tool_call', 'tool_result')
    """)
    op.execute("ALTER TYPE chatrole RENAME TO chatrole_old")
    op.execute("CREATE TYPE chatrole AS ENUM ('user', 'assistant')")
    op.execute("""
        ALTER TABLE chat_messages
            ALTER COLUMN role TYPE chatrole
            USING role::text::chatrole
    """)
    op.execute("DROP TYPE chatrole_old")
