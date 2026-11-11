"""Persist controlled API case execution results.

Revision ID: 0005_api_case_evaluations
Revises: 0004_execution_runs
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0005_api_case_evaluations"
down_revision: Union[str, None] = "0004_execution_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_case_evaluations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(length=36),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("execution_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_id", sa.String(length=80), nullable=False),
        sa.Column("oracle_version", sa.String(length=80), nullable=False),
        sa.Column("suite_hash", sa.String(length=71), nullable=False),
        sa.Column(
            "result_json",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_api_case_evaluations_task_id", "api_case_evaluations", ["task_id"]
    )
    op.create_index(
        "ix_api_case_evaluations_run_id", "api_case_evaluations", ["run_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_api_case_evaluations_run_id", table_name="api_case_evaluations")
    op.drop_index("ix_api_case_evaluations_task_id", table_name="api_case_evaluations")
    op.drop_table("api_case_evaluations")