"""add_project_data_sources_table

Revision ID: 640c819eb8c0
Revises: 668b0c9e67b2
Create Date: 2026-06-14 11:44:06.406520

"""

import json
import uuid
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "640c819eb8c0"
down_revision: Union[str, Sequence[str], None] = "668b0c9e67b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_data_sources",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(), nullable=False, server_default="flow_package"),
        sa.Column("data_source_id", sa.String(), nullable=False),
        sa.Column("data_source_name", sa.String(), nullable=False, server_default=""),
        sa.Column("sanitized_name", sa.String(), nullable=False, server_default=""),
        sa.Column("queries", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("params_info", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("can_run_without_input", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("data_schema", sa.String(), nullable=False, server_default=""),
        sa.Column("relevant_fields", sa.String(), nullable=False, server_default=""),
        sa.Column("data_characteristics", sa.String(), nullable=False, server_default=""),
        sa.Column("integration_notes", sa.String(), nullable=False, server_default=""),
        sa.Column("param_ux_hints", sa.String(), nullable=False, server_default=""),
        sa.UniqueConstraint("project_id", "type", "data_source_id", name="uq_project_data_source"),
    )
    op.create_index("ix_project_data_sources_project_id", "project_data_sources", ["project_id"])

    # Migrate existing data from projects.data_sources JSON column
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, data_sources FROM projects")).fetchall()
    for project_id, raw in rows:
        if not raw:
            continue
        data_sources = json.loads(raw) if isinstance(raw, str) else raw
        if not data_sources:
            continue
        for ds in data_sources:
            ds_id = ds.get("data_source_id")
            if not ds_id:
                continue
            conn.execute(
                sa.text("""
                    INSERT INTO project_data_sources
                        (id, project_id, type, data_source_id, data_source_name, sanitized_name,
                         queries, params_info, can_run_without_input, data_schema,
                         relevant_fields, data_characteristics, integration_notes, param_ux_hints)
                    VALUES
                        (:id, :project_id, :type, :data_source_id, :data_source_name, :sanitized_name,
                         :queries, :params_info, :can_run_without_input, :data_schema,
                         :relevant_fields, :data_characteristics, :integration_notes, :param_ux_hints)
                    ON CONFLICT (project_id, type, data_source_id) DO NOTHING
                """),
                {
                    "id": str(uuid.uuid4()),
                    "project_id": project_id,
                    "type": "flow_package",
                    "data_source_id": ds_id,
                    "data_source_name": ds.get("data_source_name", ""),
                    "sanitized_name": ds.get("sanitized_name", ""),
                    "queries": json.dumps(ds.get("queries", [])),
                    "params_info": json.dumps(ds.get("params_info", {})),
                    "can_run_without_input": ds.get("can_run_without_input", False),
                    "data_schema": ds.get("data_schema", ""),
                    "relevant_fields": ds.get("relevant_fields", ""),
                    "data_characteristics": ds.get("data_characteristics", ""),
                    "integration_notes": ds.get("integration_notes", ""),
                    "param_ux_hints": ds.get("param_ux_hints", ""),
                },
            )

    op.drop_column("projects", "data_sources")


def downgrade() -> None:
    op.add_column("projects", sa.Column("data_sources", sa.JSON(), nullable=True))
    op.drop_table("project_data_sources")
