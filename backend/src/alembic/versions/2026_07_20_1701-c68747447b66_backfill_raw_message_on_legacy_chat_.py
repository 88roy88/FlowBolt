"""add raw_message column, backfill legacy rows, simplify ChatRole enum

Revision ID: c68747447b66
Revises: a1b2c3d4e5f6
Create Date: 2026-07-20 17:01:35.205162

"""

import json
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c68747447b66"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# tool name -> name of its first (and only recoverable) argument, per the tools'
# real signatures in followup/agent.py and fix_error/agent.py.
TOOL_FIRST_ARG = {
    "grep": "pattern",
    "glob": "pattern",
    "read_file": "path",
    "write_file": "path",
    "edit_file": "path",
    "fix_error": "file",
}

REDACTED = "[redacted]"


def _parse_tool_call_content(content: str) -> tuple[str, str | None]:
    if " on " not in content:
        return content, None
    tool, _, rest = content.partition(" on ")
    if rest.startswith("'") and rest.endswith("'"):
        rest = rest[1:-1]
    return tool, rest


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("raw_message", sa.JSON(), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, project_id, role, content, raw_message FROM chat_messages ORDER BY project_id, created_at")
    ).fetchall()

    pending_reasoning: str | None = None
    last_project_id: str | None = None

    for row_id, _project_id, role, content, raw_message in rows:
        if _project_id != last_project_id:
            pending_reasoning = None
            last_project_id = _project_id

        if raw_message is not None:
            pending_reasoning = None
            continue

        if role == "reasoning":
            pending_reasoning = content
            continue

        if role == "assistant":
            new_raw_message = {"role": "assistant", "content": content}
            conn.execute(
                sa.text("UPDATE chat_messages SET raw_message = :raw_message WHERE id = :id"),
                {"raw_message": json.dumps(new_raw_message), "id": row_id},
            )
            pending_reasoning = None
            continue

        if role == "tool_call":
            tool, arg_value = _parse_tool_call_content(content)
            arg_key = TOOL_FIRST_ARG.get(tool)
            args = {arg_key: arg_value} if arg_key and arg_value is not None else {}
            args["_other_args"] = REDACTED
            new_raw_message = {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": row_id, "type": "function", "function": {"name": tool, "arguments": json.dumps(args)}}
                ],
            }
            if pending_reasoning:
                new_raw_message["reasoning_content"] = pending_reasoning
            conn.execute(
                sa.text("UPDATE chat_messages SET raw_message = :raw_message WHERE id = :id"),
                {"raw_message": json.dumps(new_raw_message), "id": row_id},
            )
            pending_reasoning = None
            continue

        if role == "tool_result":
            # Pairs 1:1 with the immediately preceding tool_call row (see _chat_agent.py's
            # legacy save order), whose synthesized tool_calls[0].id we just set to its own row id.
            preceding_tool_call_id = conn.execute(
                sa.text(
                    "SELECT id FROM chat_messages WHERE project_id = :project_id AND role = 'tool_call' "
                    "AND created_at < (SELECT created_at FROM chat_messages WHERE id = :id) "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"project_id": _project_id, "id": row_id},
            ).scalar()
            if preceding_tool_call_id is None:
                continue
            new_raw_message = {"role": "tool", "tool_call_id": preceding_tool_call_id, "content": content}
            conn.execute(
                sa.text("UPDATE chat_messages SET raw_message = :raw_message WHERE id = :id"),
                {"raw_message": json.dumps(new_raw_message), "id": row_id},
            )

    op.execute(sa.text("DELETE FROM chat_messages WHERE role = 'reasoning'"))

    # Add the new 'tool' value to the Postgres enum before renaming rows
    op.execute(sa.text("ALTER TYPE chatrole ADD VALUE IF NOT EXISTS 'tool'"))
    # Commit the enum change — ALTER TYPE ... ADD VALUE can't run inside a transaction in PG
    op.execute(sa.text("COMMIT"))

    op.execute(sa.text("UPDATE chat_messages SET role = 'assistant' WHERE role = 'tool_call'"))
    op.execute(sa.text("UPDATE chat_messages SET role = 'tool' WHERE role = 'tool_result'"))

    # Recreate the enum with only the valid values now that no rows use the old ones
    op.execute(sa.text("ALTER TABLE chat_messages ALTER COLUMN role TYPE VARCHAR"))
    op.execute(sa.text("DROP TYPE chatrole"))
    op.execute(sa.text("CREATE TYPE chatrole AS ENUM ('user', 'assistant', 'tool')"))
    op.execute(sa.text("ALTER TABLE chat_messages ALTER COLUMN role TYPE chatrole USING role::chatrole"))


def downgrade() -> None:
    # Restore old enum values and role assignments
    op.execute(sa.text("ALTER TABLE chat_messages ALTER COLUMN role TYPE VARCHAR"))
    op.execute(sa.text("DROP TYPE chatrole"))
    op.execute(sa.text("CREATE TYPE chatrole AS ENUM ('user', 'assistant', 'tool_call', 'tool_result', 'reasoning')"))
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE chat_messages SET role = 'tool_call' WHERE role = 'assistant' AND raw_message LIKE '%tool_calls%'"
        )
    )
    conn.execute(sa.text("UPDATE chat_messages SET role = 'tool_result' WHERE role = 'tool'"))
    op.execute(sa.text("ALTER TABLE chat_messages ALTER COLUMN role TYPE chatrole USING role::chatrole"))
    op.drop_column("chat_messages", "raw_message")
