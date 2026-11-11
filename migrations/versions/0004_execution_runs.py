"""Add calibrated execution run records.

Revision ID: 0004_execution_runs
Revises: 0003_assurance_reports
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004_execution_runs"
down_revision: Union[str, None] = "0003_assurance_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "execution_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(length=36),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("intent_version", sa.Integer(), nullable=False),
        sa.Column("calibration_version", sa.String(length=40), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("prompt_hash", sa.String(length=71), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("model", sa.String(length=200), nullable=True),
        sa.Column(
            "usage_json",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "output_id",
            sa.String(length=36),
            sa.ForeignKey("outputs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "assurance_report_id",
            sa.String(length=36),
            sa.ForeignKey("assurance_reports.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_execution_runs_task_id", "execution_runs", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_execution_runs_task_id", table_name="execution_runs")
    op.drop_table("execution_runs")