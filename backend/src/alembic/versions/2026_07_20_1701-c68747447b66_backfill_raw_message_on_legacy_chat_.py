"""backfill raw_message on legacy chat_messages and drop reasoning role

Legacy rows only ever stored a human-readable summary (e.g. "read_file on
'/src/App.tsx'" or an 80-char truncated result preview), never the literal
LLM message. This reconstructs a best-effort raw_message for each role:

- assistant: lossless — {"role": "assistant", "content": <content>}.
- reasoning: not its own row — folded into the *next* tool_call row's
  synthesized message as `reasoning_content` (this mirrors how it was
  produced originally: reasoning_content always preceded that iteration's
  tool_calls in the same LLM turn). The `reasoning` role itself is dropped.
- tool_call: content only ever recorded one argument (picked positionally,
  no key name). The key is recovered from the tool's real signature (stable
  across the codebase's history); every other real argument is unknown and
  filled with "[redacted]".
- tool_result: content is an 80-char-truncated preview; there is no way to
  recover the full original tool output.

Revision ID: c68747447b66
Revises: 7dcb5315f9e0
Create Date: 2026-07-20 17:01:35.205162

"""

import json
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c68747447b66"
down_revision: Union[str, Sequence[str], None] = "7dcb5315f9e0"
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


def downgrade() -> None:
    # Only reverses the raw_message backfill on tool_call/tool_result/assistant rows this
    # migration touched. `reasoning` rows are not resurrected — their original position
    # relative to other rows can't be recovered, only the content folded into a tool_call's
    # reasoning_content, which this intentionally discards on downgrade.
    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE chat_messages SET raw_message = NULL WHERE role IN ('assistant', 'tool_call', 'tool_result')")
    )
