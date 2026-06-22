"""Initial schema for BuQue P0 tables."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dim_sku",
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("product_name", sa.String(length=255), nullable=True),
        sa.Column("item_grade", sa.String(length=16), nullable=True),
        sa.Column("seasonality", sa.String(length=32), nullable=True),
        sa.Column("category", sa.String(length=128), nullable=True),
        sa.Column("is_key_listing", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_focus_sku", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("sku"),
    )
    op.create_table(
        "dim_msku_mapping",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("msku", sa.String(length=128), nullable=False),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("store", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(["sku"], ["dim_sku.sku"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("msku", "channel", name="uq_msku_channel"),
    )
    op.create_index("ix_dim_msku_mapping_msku", "dim_msku_mapping", ["msku"])
    op.create_index("ix_dim_msku_mapping_sku", "dim_msku_mapping", ["sku"])

    monitoring_scope = postgresql.ENUM(
        "GLOBAL", "WAREHOUSE", "CHANNEL", name="monitoringscope", create_type=False
    )
    risk_type = postgresql.ENUM(
        "STOCKOUT",
        "SLOW_MOVING",
        "SALES_ANOMALY",
        "FORECAST_BIAS",
        "DATA_ANOMALY",
        name="risktype",
        create_type=False,
    )
    risk_level = postgresql.ENUM(
        "GREEN", "YELLOW", "ORANGE", "RED", name="risklevel", create_type=False
    )
    monitoring_scope.create(op.get_bind(), checkfirst=True)
    risk_type.create(op.get_bind(), checkfirst=True)
    risk_level.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "fact_sales_daily",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("msku", sa.String(length=128), nullable=False),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=True),
        sa.Column("warehouse", sa.String(length=128), nullable=True),
        sa.Column("order_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["sku"], ["dim_sku.sku"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date", "msku", "channel", name="uq_sales_daily"),
    )
    op.create_index("ix_fact_sales_daily_date", "fact_sales_daily", ["date"])
    op.create_index("ix_sales_sku_date", "fact_sales_daily", ["sku", "date"])

    op.create_table(
        "fact_inventory_daily",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("warehouse", sa.String(length=128), nullable=False),
        sa.Column("available_inventory", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reserved_inventory", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("on_hand_inventory", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("in_transit_no_eta", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ref_daily_sales", sa.Numeric(12, 4), nullable=True),
        sa.Column("turnover_days", sa.Numeric(12, 2), nullable=True),
        sa.ForeignKeyConstraint(["sku"], ["dim_sku.sku"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date", "sku", "warehouse", name="uq_inventory_daily"),
    )
    op.create_index("ix_fact_inventory_daily_date", "fact_inventory_daily", ["date"])
    op.create_index("ix_fact_inventory_daily_sku", "fact_inventory_daily", ["sku"])

    op.create_table(
        "fact_inbound_batch",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("warehouse", sa.String(length=128), nullable=False),
        sa.Column("batch_id", sa.String(length=128), nullable=False),
        sa.Column("eta_date", sa.Date(), nullable=True),
        sa.Column("tms_status", sa.String(length=32), nullable=True),
        sa.Column("unreceived_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("eligible_for_relief", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(["sku"], ["dim_sku.sku"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date", "sku", "warehouse", "batch_id", name="uq_inbound_batch"),
    )
    op.create_index("ix_fact_inbound_batch_date", "fact_inbound_batch", ["date"])
    op.create_index("ix_fact_inbound_batch_sku", "fact_inbound_batch", ["sku"])

    op.create_table(
        "fact_forecast_version",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("forecast_daily", sa.Numeric(12, 4), nullable=True),
        sa.ForeignKeyConstraint(["sku"], ["dim_sku.sku"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date", "sku", "version", name="uq_forecast_version"),
    )
    op.create_index("ix_fact_forecast_version_date", "fact_forecast_version", ["date"])
    op.create_index("ix_fact_forecast_version_sku", "fact_forecast_version", ["sku"])

    op.create_table(
        "rule_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rule_code", sa.String(length=64), nullable=False),
        sa.Column("rule_name", sa.String(length=128), nullable=False),
        sa.Column("param_value", sa.String(length=255), nullable=False),
        sa.Column("param_type", sa.String(length=32), nullable=False, server_default="string"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("proposer", sa.String(length=64), nullable=True),
        sa.Column("approver", sa.String(length=64), nullable=True),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_code", "version", name="uq_rule_config"),
    )
    op.create_index("ix_rule_config_rule_code", "rule_config", ["rule_code"])

    handling_status = postgresql.ENUM(
        "UNPROCESSED", "PROCESSING", "HANDLED", name="handlingstatus", create_type=False
    )
    handling_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "fact_monitor_result",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("warehouse", sa.String(length=128), nullable=True),
        sa.Column("channel", sa.String(length=64), nullable=True),
        sa.Column("scope", monitoring_scope, nullable=False),
        sa.Column("risk_type", risk_type, nullable=False),
        sa.Column("risk_level", risk_level, nullable=False),
        sa.Column("trigger_rule", sa.String(length=64), nullable=False),
        sa.Column("trigger_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("dos", sa.Numeric(12, 2), nullable=True),
        sa.Column("ref_daily_sales", sa.Numeric(12, 4), nullable=True),
        sa.Column("available_inventory", sa.Integer(), nullable=True),
        sa.Column("inbound_relief_applied", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("relief_note", sa.String(length=255), nullable=True),
        sa.Column("requires_explanation", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("requires_human_confirm", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("handling_status", handling_status, nullable=False, server_default="UNPROCESSED"),
        sa.ForeignKeyConstraint(["sku"], ["dim_sku.sku"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date", "sku", "warehouse", "scope", "risk_type", name="uq_monitor_result"),
    )
    op.create_index("ix_fact_monitor_result_date", "fact_monitor_result", ["date"])
    op.create_index("ix_fact_monitor_result_sku", "fact_monitor_result", ["sku"])

    op.create_table(
        "event_pool",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("warehouse", sa.String(length=128), nullable=True),
        sa.Column("risk_type", risk_type, nullable=False),
        sa.Column("risk_level", risk_level, nullable=False),
        sa.Column("trigger_rule", sa.String(length=64), nullable=False),
        sa.Column("trigger_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("evidence_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("require_human_confirm", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("monitor_result_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["monitor_result_id"], ["fact_monitor_result.id"]),
        sa.ForeignKeyConstraint(["sku"], ["dim_sku.sku"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_event_id"),
    )
    op.create_index("ix_event_pool_date", "event_pool", ["date"])
    op.create_index("ix_event_pool_sku", "event_pool", ["sku"])

    op.create_table(
        "fact_agent_explain",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("primary_explanation", sa.Text(), nullable=False),
        sa.Column("secondary_explanation", sa.Text(), nullable=True),
        sa.Column("tertiary_explanation", sa.Text(), nullable=True),
        sa.Column("explanation_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("key_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("suggested_action", sa.Text(), nullable=False),
        sa.Column("responsible_role", sa.String(length=64), nullable=False),
        sa.Column("action_deadline", sa.String(length=64), nullable=True),
        sa.Column("require_human_confirm", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("confidence_note", sa.Text(), nullable=True),
        sa.Column("raw_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["sku"], ["dim_sku.sku"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date", "sku", "event_id", name="uq_agent_explain"),
    )
    op.create_index("ix_fact_agent_explain_date", "fact_agent_explain", ["date"])
    op.create_index("ix_fact_agent_explain_sku", "fact_agent_explain", ["sku"])

    feedback_decision = postgresql.ENUM(
        "ADOPTED", "REJECTED", "PARTIAL", name="feedbackdecision", create_type=False
    )
    feedback_decision.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "fact_feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("risk_type", risk_type, nullable=False),
        sa.Column("agent_suggested_action", sa.Text(), nullable=True),
        sa.Column("manual_conclusion", sa.Text(), nullable=True),
        sa.Column("decision", feedback_decision, nullable=False),
        sa.Column("reason_tag", sa.String(length=128), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("handling_status", handling_status, nullable=False, server_default="HANDLED"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["sku"], ["dim_sku.sku"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fact_feedback_date", "fact_feedback", ["date"])
    op.create_index("ix_fact_feedback_sku", "fact_feedback", ["sku"])

    ingestion_status = postgresql.ENUM(
        "RUNNING", "SUCCESS", "FAILED", name="ingestionstatus", create_type=False
    )
    ingestion_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "ingestion_run",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", ingestion_status, nullable=False, server_default="RUNNING"),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("file_hash", sa.String(length=64), nullable=True),
        sa.Column("file_path", sa.String(length=512), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "data_quality_issue",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=True),
        sa.Column("warehouse", sa.String(length=128), nullable=True),
        sa.Column("issue_code", sa.String(length=64), nullable=False),
        sa.Column("issue_message", sa.Text(), nullable=False),
        sa.Column("field_name", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_quality_issue_date", "data_quality_issue", ["date"])
    op.create_index("ix_data_quality_issue_sku", "data_quality_issue", ["sku"])


def downgrade() -> None:
    op.drop_table("data_quality_issue")
    op.drop_table("ingestion_run")
    op.drop_table("fact_feedback")
    op.drop_table("fact_agent_explain")
    op.drop_table("event_pool")
    op.drop_table("fact_monitor_result")
    op.drop_table("rule_config")
    op.drop_table("fact_forecast_version")
    op.drop_table("fact_inbound_batch")
    op.drop_table("fact_inventory_daily")
    op.drop_table("fact_sales_daily")
    op.drop_table("dim_msku_mapping")
    op.drop_table("dim_sku")
    for name in (
        "ingestionstatus",
        "feedbackdecision",
        "handlingstatus",
        "risklevel",
        "risktype",
        "monitoringscope",
    ):
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
