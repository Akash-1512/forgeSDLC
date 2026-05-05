"""Initial schema — pipeline_runs, user_preferences, post_mortems tables.

Revision ID: 001
Revises: —
Create Date: 2026-04-01

This migration creates the baseline schema shipped in v1.0.0.
If tables already exist (created via init_db()/create_all()), Alembic will
detect no changes on next autogenerate — this is intentional.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pipeline_runs",
        sa.Column("run_id", sa.String(), nullable=False, primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False, index=True),
        sa.Column("user_prompt", sa.Text(), nullable=False),
        sa.Column("stack_chosen", sa.String(), nullable=True),
        sa.Column("deployment_success", sa.Boolean(), nullable=True),
        sa.Column("cost_total_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("hitl_rounds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("human_corrections", JSONB(), nullable=False, server_default="[]"),
        sa.Column("lessons_learned", JSONB(), nullable=False, server_default="[]"),
        sa.Column("tool_delegated_to", sa.String(), nullable=True),
        sa.Column("workspace_path", sa.String(), nullable=False, server_default="."),
    )

    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.String(), nullable=False, primary_key=True),
        sa.Column("preferred_code_gen_tool", sa.String(), nullable=False),
        sa.Column("preferred_stack", JSONB(), nullable=False, server_default="[]"),
        sa.Column("subscription_tier", sa.String(), nullable=False, server_default="free"),
        sa.Column("byok_providers", JSONB(), nullable=False, server_default="[]"),
        sa.Column("recurring_security_findings", JSONB(), nullable=False, server_default="[]"),
        sa.Column("recurring_anti_patterns", JSONB(), nullable=False, server_default="[]"),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "post_mortems",
        sa.Column("post_mortem_id", sa.String(), nullable=False, primary_key=True),
        sa.Column("run_id", sa.String(), nullable=False, index=True),
        sa.Column("failure_type", sa.String(), nullable=False),
        sa.Column("agent_that_failed", sa.String(), nullable=False),
        sa.Column("root_cause", sa.String(), nullable=False),
        sa.Column("resolution", sa.String(), nullable=False),
        sa.Column("prevention_rule", sa.String(), nullable=False),
        sa.Column("stack_context", sa.String(), nullable=False),
        sa.Column("tool_involved", sa.String(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table("post_mortems")
    op.drop_table("user_preferences")
    op.drop_table("pipeline_runs")
