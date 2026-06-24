import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from buque.db import Base


class MonitoringScope(str, enum.Enum):
    GLOBAL = "GLOBAL"
    WAREHOUSE = "WAREHOUSE"
    CHANNEL = "CHANNEL"


class RiskType(str, enum.Enum):
    STOCKOUT = "STOCKOUT"
    SLOW_MOVING = "SLOW_MOVING"
    SALES_ANOMALY = "SALES_ANOMALY"
    FORECAST_BIAS = "FORECAST_BIAS"
    DATA_ANOMALY = "DATA_ANOMALY"


class RiskLevel(str, enum.Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    RED = "RED"


class IngestionStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class FeedbackDecision(str, enum.Enum):
    ADOPTED = "ADOPTED"
    REJECTED = "REJECTED"
    PARTIAL = "PARTIAL"


class HandlingStatus(str, enum.Enum):
    UNPROCESSED = "UNPROCESSED"
    PROCESSING = "PROCESSING"
    HANDLED = "HANDLED"


class DimSku(Base):
    __tablename__ = "dim_sku"

    sku: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_name: Mapped[str | None] = mapped_column(String(255))
    item_grade: Mapped[str | None] = mapped_column(String(16))
    seasonality: Mapped[str | None] = mapped_column(String(32))
    category: Mapped[str | None] = mapped_column(String(128))
    is_key_listing: Mapped[bool] = mapped_column(Boolean, default=False)
    is_focus_sku: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DimMskuMapping(Base):
    __tablename__ = "dim_msku_mapping"
    __table_args__ = (UniqueConstraint("msku", "channel", name="uq_msku_channel"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    msku: Mapped[str] = mapped_column(String(128), index=True)
    channel: Mapped[str] = mapped_column(String(64))
    sku: Mapped[str] = mapped_column(String(64), ForeignKey("dim_sku.sku"), index=True)
    store: Mapped[str | None] = mapped_column(String(128))


class FactSalesDaily(Base):
    __tablename__ = "fact_sales_daily"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "date", "msku", "channel", name="uq_sales_daily"),
        Index("ix_sales_sku_date", "sku", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_sync_job.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    msku: Mapped[str] = mapped_column(String(128))
    channel: Mapped[str] = mapped_column(String(64))
    sku: Mapped[str | None] = mapped_column(String(64), ForeignKey("dim_sku.sku"), index=True)
    warehouse: Mapped[str | None] = mapped_column(String(128))
    order_qty: Mapped[int] = mapped_column(Integer, default=0)


class FactInventoryDaily(Base):
    __tablename__ = "fact_inventory_daily"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "sku", "warehouse", name="uq_inventory_daily"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_sync_job.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    sku: Mapped[str] = mapped_column(String(64), ForeignKey("dim_sku.sku"), index=True)
    warehouse: Mapped[str] = mapped_column(String(128))
    available_inventory: Mapped[int] = mapped_column(Integer, default=0)
    reserved_inventory: Mapped[int] = mapped_column(Integer, default=0)
    on_hand_inventory: Mapped[int] = mapped_column(Integer, default=0)
    in_transit_no_eta: Mapped[int] = mapped_column(Integer, default=0)
    ref_daily_sales: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    turnover_days: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))


class FactInboundBatch(Base):
    __tablename__ = "fact_inbound_batch"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id", "sku", "warehouse", "batch_id", name="uq_inbound_batch"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_sync_job.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    sku: Mapped[str] = mapped_column(String(64), ForeignKey("dim_sku.sku"), index=True)
    warehouse: Mapped[str] = mapped_column(String(128))
    batch_id: Mapped[str] = mapped_column(String(128))
    eta_date: Mapped[date | None] = mapped_column(Date)
    tms_status: Mapped[str | None] = mapped_column(String(32))
    unreceived_qty: Mapped[int] = mapped_column(Integer, default=0)
    eligible_for_relief: Mapped[bool] = mapped_column(Boolean, default=False)


class FactForecastVersion(Base):
    __tablename__ = "fact_forecast_version"
    __table_args__ = (UniqueConstraint("date", "sku", "version", name="uq_forecast_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    sku: Mapped[str] = mapped_column(String(64), ForeignKey("dim_sku.sku"), index=True)
    version: Mapped[str] = mapped_column(String(64))
    forecast_daily: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))


class RuleConfig(Base):
    __tablename__ = "rule_config"
    __table_args__ = (UniqueConstraint("rule_code", "version", name="uq_rule_config"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_code: Mapped[str] = mapped_column(String(64), index=True)
    rule_name: Mapped[str] = mapped_column(String(128))
    param_value: Mapped[str] = mapped_column(String(255))
    param_type: Mapped[str] = mapped_column(String(32), default="string")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    effective_date: Mapped[date] = mapped_column(Date)
    proposer: Mapped[str | None] = mapped_column(String(64))
    approver: Mapped[str | None] = mapped_column(String(64))
    change_reason: Mapped[str | None] = mapped_column(Text)


class FactMonitorResult(Base):
    __tablename__ = "fact_monitor_result"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "sku",
            "warehouse",
            "scope",
            "risk_type",
            name="uq_monitor_result",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_sync_job.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    sku: Mapped[str] = mapped_column(String(64), ForeignKey("dim_sku.sku"), index=True)
    warehouse: Mapped[str | None] = mapped_column(String(128))
    channel: Mapped[str | None] = mapped_column(String(64))
    scope: Mapped[MonitoringScope] = mapped_column(Enum(MonitoringScope))
    risk_type: Mapped[RiskType] = mapped_column(Enum(RiskType))
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel))
    trigger_rule: Mapped[str] = mapped_column(String(64))
    trigger_metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    dos: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    ref_daily_sales: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    available_inventory: Mapped[int | None] = mapped_column(Integer)
    inbound_relief_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    relief_note: Mapped[str | None] = mapped_column(String(255))
    requires_explanation: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_human_confirm: Mapped[bool] = mapped_column(Boolean, default=False)
    handling_status: Mapped[HandlingStatus] = mapped_column(
        Enum(HandlingStatus), default=HandlingStatus.UNPROCESSED
    )


class EventPool(Base):
    __tablename__ = "event_pool"
    __table_args__ = (UniqueConstraint("event_id", name="uq_event_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_sync_job.id"), index=True)
    event_id: Mapped[str] = mapped_column(String(64))
    date: Mapped[date] = mapped_column(Date, index=True)
    sku: Mapped[str] = mapped_column(String(64), ForeignKey("dim_sku.sku"), index=True)
    warehouse: Mapped[str | None] = mapped_column(String(128))
    risk_type: Mapped[RiskType] = mapped_column(Enum(RiskType))
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel))
    trigger_rule: Mapped[str] = mapped_column(String(64))
    trigger_metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    evidence_context: Mapped[dict] = mapped_column(JSONB, default=dict)
    require_human_confirm: Mapped[bool] = mapped_column(Boolean, default=True)
    monitor_result_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("fact_monitor_result.id")
    )


class FactAgentExplain(Base):
    __tablename__ = "fact_agent_explain"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "sku", "event_id", name="uq_agent_explain"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_sync_job.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    sku: Mapped[str] = mapped_column(String(64), ForeignKey("dim_sku.sku"), index=True)
    event_id: Mapped[str] = mapped_column(String(64))
    primary_explanation: Mapped[str] = mapped_column(Text)
    secondary_explanation: Mapped[str | None] = mapped_column(Text)
    tertiary_explanation: Mapped[str | None] = mapped_column(Text)
    explanation_tags: Mapped[list] = mapped_column(JSONB, default=list)
    key_evidence: Mapped[list] = mapped_column(JSONB, default=list)
    suggested_action: Mapped[str] = mapped_column(Text)
    responsible_role: Mapped[str] = mapped_column(String(64))
    action_deadline: Mapped[str | None] = mapped_column(String(64))
    require_human_confirm: Mapped[bool] = mapped_column(Boolean, default=True)
    confidence_note: Mapped[str | None] = mapped_column(Text)
    raw_response: Mapped[dict | None] = mapped_column(JSONB)


class FactFeedback(Base):
    __tablename__ = "fact_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    sku: Mapped[str] = mapped_column(String(64), ForeignKey("dim_sku.sku"), index=True)
    risk_type: Mapped[RiskType] = mapped_column(Enum(RiskType))
    agent_suggested_action: Mapped[str | None] = mapped_column(Text)
    manual_conclusion: Mapped[str | None] = mapped_column(Text)
    decision: Mapped[FeedbackDecision] = mapped_column(Enum(FeedbackDecision))
    reason_tag: Mapped[str | None] = mapped_column(String(128))
    remark: Mapped[str | None] = mapped_column(Text)
    handling_status: Mapped[HandlingStatus] = mapped_column(
        Enum(HandlingStatus), default=HandlingStatus.HANDLED
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IngestionRun(Base):
    __tablename__ = "ingestion_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[IngestionStatus] = mapped_column(
        Enum(IngestionStatus), default=IngestionStatus.RUNNING
    )
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    file_hash: Mapped[str | None] = mapped_column(String(64))
    file_path: Mapped[str | None] = mapped_column(String(512))
    error_message: Mapped[str | None] = mapped_column(Text)


class ErpSyncPhase(str, enum.Enum):
    EXPORTING = "EXPORTING"
    INGESTING = "INGESTING"
    QUALITY = "QUALITY"
    RULES = "RULES"
    EVENTS = "EVENTS"
    EXPLAIN = "EXPLAIN"
    DONE = "DONE"


class JobKind(str, enum.Enum):
    SYNC = "SYNC"
    ANALYSIS = "ANALYSIS"
    PIPELINE = "PIPELINE"


class ErpSyncJob(Base):
    __tablename__ = "erp_sync_job"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    monitor_date: Mapped[date] = mapped_column(Date, index=True)
    job_kind: Mapped[JobKind] = mapped_column(Enum(JobKind), default=JobKind.SYNC)
    phase: Mapped[ErpSyncPhase] = mapped_column(
        Enum(ErpSyncPhase, native_enum=False, length=32),
        default=ErpSyncPhase.EXPORTING,
    )
    status: Mapped[IngestionStatus] = mapped_column(
        Enum(IngestionStatus), default=IngestionStatus.RUNNING
    )
    phase_message: Mapped[str | None] = mapped_column(String(255))
    error_message: Mapped[str | None] = mapped_column(Text)
    sync_summary: Mapped[dict | None] = mapped_column(JSON)
    analysis_summary: Mapped[dict | None] = mapped_column(JSON)
    progress_current: Mapped[int | None] = mapped_column(Integer)
    progress_total: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ErpSyncLog(Base):
    __tablename__ = "erp_sync_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_sync_job.id"), index=True)
    level: Mapped[str] = mapped_column(String(16), default="INFO")
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DataQualityIssue(Base):
    __tablename__ = "data_quality_issue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_sync_job.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    sku: Mapped[str | None] = mapped_column(String(64), index=True)
    warehouse: Mapped[str | None] = mapped_column(String(128))
    issue_code: Mapped[str] = mapped_column(String(64))
    issue_message: Mapped[str] = mapped_column(Text)
    field_name: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
