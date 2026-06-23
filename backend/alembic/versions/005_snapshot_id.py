"""Add PIPELINE job kind and snapshot_id on fact tables."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_snapshot_id"
down_revision: Union[str, None] = "004_legacy_analyzing_phase"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SNAPSHOT_TABLES = (
    "fact_inventory_daily",
    "fact_sales_daily",
    "fact_inbound_batch",
    "fact_monitor_result",
    "event_pool",
    "fact_agent_explain",
    "data_quality_issue",
)


def _dedupe_keep_latest(table: str, partition_cols: tuple[str, ...]) -> None:
    """Legacy backfill uses one snapshot; keep the newest business-day row per partition."""
    cols = ", ".join(partition_cols)
    op.execute(
        f"""
        DELETE FROM {table}
        WHERE id NOT IN (
            SELECT DISTINCT ON ({cols}) id
            FROM {table}
            ORDER BY {cols}, date DESC, id DESC
        )
        """
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # PostgreSQL: new enum values must be committed before use in the same session.
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE jobkind ADD VALUE IF NOT EXISTS 'PIPELINE'")

    for table in SNAPSHOT_TABLES:
        op.add_column(table, sa.Column("snapshot_id", sa.Integer(), nullable=True))

    op.execute(
        """
        INSERT INTO erp_sync_job (
            monitor_date, job_kind, phase, status, phase_message, started_at, finished_at
        )
        SELECT
            COALESCE((SELECT MAX(date) FROM fact_monitor_result), CURRENT_DATE),
            'PIPELINE',
            'DONE',
            'SUCCESS',
            'legacy migration',
            NOW(),
            NOW()
        """
    )
    op.execute(
        """
        UPDATE fact_inventory_daily SET snapshot_id = (SELECT MAX(id) FROM erp_sync_job WHERE job_kind = 'PIPELINE')
        WHERE snapshot_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE fact_sales_daily SET snapshot_id = (SELECT MAX(id) FROM erp_sync_job WHERE job_kind = 'PIPELINE')
        WHERE snapshot_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE fact_inbound_batch SET snapshot_id = (SELECT MAX(id) FROM erp_sync_job WHERE job_kind = 'PIPELINE')
        WHERE snapshot_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE fact_monitor_result SET snapshot_id = (SELECT MAX(id) FROM erp_sync_job WHERE job_kind = 'PIPELINE')
        WHERE snapshot_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE event_pool SET snapshot_id = (SELECT MAX(id) FROM erp_sync_job WHERE job_kind = 'PIPELINE')
        WHERE snapshot_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE fact_agent_explain SET snapshot_id = (SELECT MAX(id) FROM erp_sync_job WHERE job_kind = 'PIPELINE')
        WHERE snapshot_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE data_quality_issue SET snapshot_id = (SELECT MAX(id) FROM erp_sync_job WHERE job_kind = 'PIPELINE')
        WHERE snapshot_id IS NULL
        """
    )

    # Single legacy snapshot collapses multi-day rows; dedupe before new unique keys.
    op.execute(
        """
        UPDATE event_pool
        SET monitor_result_id = NULL
        WHERE monitor_result_id IS NOT NULL
          AND monitor_result_id NOT IN (
              SELECT DISTINCT ON (snapshot_id, sku, warehouse, scope, risk_type) id
              FROM fact_monitor_result
              ORDER BY snapshot_id, sku, warehouse, scope, risk_type, date DESC, id DESC
          )
        """
    )
    _dedupe_keep_latest("fact_monitor_result", ("snapshot_id", "sku", "warehouse", "scope", "risk_type"))
    _dedupe_keep_latest("fact_inventory_daily", ("snapshot_id", "sku", "warehouse"))
    _dedupe_keep_latest("fact_inbound_batch", ("snapshot_id", "sku", "warehouse", "batch_id"))
    _dedupe_keep_latest("fact_agent_explain", ("snapshot_id", "sku", "event_id"))

    for table in SNAPSHOT_TABLES:
        op.alter_column(table, "snapshot_id", nullable=False)
        op.create_foreign_key(
            f"fk_{table}_snapshot_id",
            table,
            "erp_sync_job",
            ["snapshot_id"],
            ["id"],
        )
        op.create_index(f"ix_{table}_snapshot_id", table, ["snapshot_id"])

    op.drop_constraint("uq_inventory_daily", "fact_inventory_daily", type_="unique")
    op.create_unique_constraint(
        "uq_inventory_daily", "fact_inventory_daily", ["snapshot_id", "sku", "warehouse"]
    )

    op.drop_constraint("uq_sales_daily", "fact_sales_daily", type_="unique")
    op.create_unique_constraint(
        "uq_sales_daily", "fact_sales_daily", ["snapshot_id", "date", "msku", "channel"]
    )

    op.drop_constraint("uq_inbound_batch", "fact_inbound_batch", type_="unique")
    op.create_unique_constraint(
        "uq_inbound_batch",
        "fact_inbound_batch",
        ["snapshot_id", "sku", "warehouse", "batch_id"],
    )

    op.drop_constraint("uq_monitor_result", "fact_monitor_result", type_="unique")
    op.create_unique_constraint(
        "uq_monitor_result",
        "fact_monitor_result",
        ["snapshot_id", "sku", "warehouse", "scope", "risk_type"],
    )

    op.drop_constraint("uq_agent_explain", "fact_agent_explain", type_="unique")
    op.create_unique_constraint(
        "uq_agent_explain", "fact_agent_explain", ["snapshot_id", "sku", "event_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_agent_explain", "fact_agent_explain", type_="unique")
    op.create_unique_constraint(
        "uq_agent_explain", "fact_agent_explain", ["date", "sku", "event_id"]
    )

    op.drop_constraint("uq_monitor_result", "fact_monitor_result", type_="unique")
    op.create_unique_constraint(
        "uq_monitor_result",
        "fact_monitor_result",
        ["date", "sku", "warehouse", "scope", "risk_type"],
    )

    op.drop_constraint("uq_inbound_batch", "fact_inbound_batch", type_="unique")
    op.create_unique_constraint(
        "uq_inbound_batch", "fact_inbound_batch", ["date", "sku", "warehouse", "batch_id"]
    )

    op.drop_constraint("uq_sales_daily", "fact_sales_daily", type_="unique")
    op.create_unique_constraint(
        "uq_sales_daily", "fact_sales_daily", ["date", "msku", "channel"]
    )

    op.drop_constraint("uq_inventory_daily", "fact_inventory_daily", type_="unique")
    op.create_unique_constraint(
        "uq_inventory_daily", "fact_inventory_daily", ["date", "sku", "warehouse"]
    )

    for table in reversed(SNAPSHOT_TABLES):
        op.drop_index(f"ix_{table}_snapshot_id", table_name=table)
        op.drop_constraint(f"fk_{table}_snapshot_id", table, type_="foreignkey")
        op.drop_column(table, "snapshot_id")

    op.execute("DELETE FROM erp_sync_job WHERE phase_message = 'legacy migration'")
