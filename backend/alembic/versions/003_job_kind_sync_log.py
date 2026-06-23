"""Add job_kind, analysis phases, sync_summary, erp_sync_log."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_job_kind_sync_log"
down_revision: Union[str, None] = "002_erp_sync_job"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    job_kind = postgresql.ENUM("SYNC", "ANALYSIS", name="jobkind", create_type=False)
    job_kind.create(bind, checkfirst=True)

    if bind.dialect.name == "postgresql":
        op.alter_column(
            "erp_sync_job",
            "phase",
            type_=sa.String(length=32),
            existing_type=postgresql.ENUM(
                "EXPORTING",
                "INGESTING",
                "ANALYZING",
                "DONE",
                name="erpsyncphase",
            ),
            postgresql_using="phase::text",
        )

    op.add_column(
        "erp_sync_job",
        sa.Column("job_kind", job_kind, nullable=False, server_default="SYNC"),
    )
    op.add_column("erp_sync_job", sa.Column("sync_summary", sa.JSON(), nullable=True))
    op.add_column("erp_sync_job", sa.Column("analysis_summary", sa.JSON(), nullable=True))
    op.add_column("erp_sync_job", sa.Column("progress_current", sa.Integer(), nullable=True))
    op.add_column("erp_sync_job", sa.Column("progress_total", sa.Integer(), nullable=True))
    op.drop_column("erp_sync_job", "run_pipeline")

    op.create_table(
        "erp_sync_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False, server_default="INFO"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["job_id"], ["erp_sync_job.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_erp_sync_log_job_id", "erp_sync_log", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_erp_sync_log_job_id", table_name="erp_sync_log")
    op.drop_table("erp_sync_log")
    op.drop_column("erp_sync_job", "progress_total")
    op.drop_column("erp_sync_job", "progress_current")
    op.drop_column("erp_sync_job", "analysis_summary")
    op.drop_column("erp_sync_job", "sync_summary")
    op.drop_column("erp_sync_job", "job_kind")
    op.add_column(
        "erp_sync_job",
        sa.Column("run_pipeline", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        erp_sync_phase = postgresql.ENUM(
            "EXPORTING",
            "INGESTING",
            "ANALYZING",
            "DONE",
            name="erpsyncphase",
            create_type=False,
        )
        op.alter_column(
            "erp_sync_job",
            "phase",
            type_=erp_sync_phase,
            existing_type=sa.String(length=32),
            postgresql_using="phase::erpsyncphase",
        )
    postgresql.ENUM(name="jobkind").drop(bind, checkfirst=True)
