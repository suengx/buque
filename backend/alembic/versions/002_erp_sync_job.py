"""Initial schema for BuQue P0 tables."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002_erp_sync_job"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    erp_sync_phase = postgresql.ENUM(
        "EXPORTING",
        "INGESTING",
        "ANALYZING",
        "DONE",
        name="erpsyncphase",
        create_type=False,
    )
    ingestion_status = postgresql.ENUM(
        "RUNNING",
        "SUCCESS",
        "FAILED",
        name="ingestionstatus",
        create_type=False,
    )
    erp_sync_phase.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "erp_sync_job",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("monitor_date", sa.Date(), nullable=False),
        sa.Column("run_pipeline", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("phase", erp_sync_phase, nullable=False, server_default="EXPORTING"),
        sa.Column("status", ingestion_status, nullable=False, server_default="RUNNING"),
        sa.Column("phase_message", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_erp_sync_job_monitor_date", "erp_sync_job", ["monitor_date"])


def downgrade() -> None:
    op.drop_index("ix_erp_sync_job_monitor_date", table_name="erp_sync_job")
    op.drop_table("erp_sync_job")
    postgresql.ENUM(name="erpsyncphase").drop(op.get_bind(), checkfirst=True)
