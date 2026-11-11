"""Add output and assurance report records.

Revision ID: 0003_assurance_reports
Revises: 0002_clarifications
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_assurance_reports"
down_revision: Union[str, None] = "0002_clarifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "outputs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(length=36),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("intent_version", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=71), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_outputs_task_id", "outputs", ["task_id"])
    op.create_table(
        "assurance_reports",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(length=36),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "output_id",
            sa.String(length=36),
            sa.ForeignKey("outputs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("intent_version", sa.Integer(), nullable=False),
        sa.Column("overall_status", sa.String(length=40), nullable=False),
        sa.Column(
            "report_json",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_assurance_reports_task_id", "assurance_reports", ["task_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_assurance_reports_task_id", table_name="assurance_reports")
    op.drop_table("assurance_reports")
    op.drop_index("ix_outputs_task_id", table_name="outputs")
    op.drop_table("outputs")
