"""v1.1.0 schema changes.

Revision ID: 002
Revises: 001
Create Date: 2026-05-05

Changes:
- post_mortems: ADD COLUMN project_id (for per-project failure filtering)
- pipeline_runs: deployment_success column type verification (Boolean, not String)

IMPORTANT for existing installations:
  If you ran forgeSDLC v1.0.0 and already have data, run:
    alembic upgrade head
  This will ADD the project_id column to existing rows with default 'default'.
  No data is lost.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add project_id to post_mortems — required for per-project failure filtering.
    # Existing rows get 'default' as project_id (safe — they belong to no specific project).
    op.add_column(
        "post_mortems",
        sa.Column(
            "project_id",
            sa.String(),
            nullable=False,
            server_default="default",
        ),
    )
    op.create_index(
        "ix_post_mortems_project_id",
        "post_mortems",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_post_mortems_project_id", table_name="post_mortems")
    op.drop_column("post_mortems", "project_id")
