from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class SkuBrief(BaseModel):
    sku: str
    product_name: str | None = None
    item_grade: str | None = None
    seasonality: str | None = None
    is_key_listing: bool = False


class DailyReportSummary(BaseModel):
    monitor_date: date
    monitored_sku_count: int
    new_red_count: int
    new_orange_count: int
    stockout_high_risk_count: int
    slow_moving_high_risk_count: int
    sales_anomaly_count: int
    data_anomaly_count: int
    priority_today_count: int


class MonitorResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date
    sku: str
    product_name: str | None = None
    warehouse: str | None
    channel: str | None
    scope: str
    risk_type: str
    risk_level: str
    trigger_rule: str
    trigger_metrics: dict
    dos: Decimal | None
    ref_daily_sales: Decimal | None
    available_inventory: int | None
    inbound_relief_applied: bool
    relief_note: str | None
    handling_status: str
    primary_explanation: str | None = None
    suggested_action: str | None = None
    responsible_role: str | None = None


class SkuDetailOut(BaseModel):
    monitor_date: date
    sku: str
    product_name: str | None
    warehouse: str | None
    risk_type: str
    risk_level: str
    trigger_metrics: dict
    dos: Decimal | None
    primary_explanation: str | None
    secondary_explanation: str | None
    tertiary_explanation: str | None
    key_evidence: list
    suggested_action: str | None
    responsible_role: str | None
    action_deadline: str | None
    require_human_confirm: bool


class FeedbackCreate(BaseModel):
    date: date
    sku: str
    risk_type: str
    agent_suggested_action: str | None = None
    manual_conclusion: str | None = None
    decision: str
    reason_tag: str | None = None
    remark: str | None = None


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date
    sku: str
    risk_type: str
    decision: str
    reason_tag: str | None
    remark: str | None
    handling_status: str
    created_at: datetime


class FeedbackStats(BaseModel):
    total: int
    adopted: int
    rejected: int
    partial: int
    adoption_rate: float


class PaginatedAlerts(BaseModel):
    items: list[MonitorResultOut]
    total: int
    page: int
    page_size: int


class PipelineRunResult(BaseModel):
    monitor_date: date
    ingestion: dict[str, int]
    quality_issues: int
    monitor_results: int
    events: int
    explained: int


class ErpSyncRequest(BaseModel):
    monitor_date: date | None = None
    run_pipeline: bool = False


class ErpSyncAccepted(BaseModel):
    monitor_date: date
    message: str = "ERP 同步已启动"


class IngestionSourceStatus(BaseModel):
    source: str
    status: str
    row_count: int
    file_path: str | None = None
    error: str | None = None
    finished_at: datetime | None = None
    ingestion_run_id: int | None = None


class ErpSyncStatusResponse(BaseModel):
    monitor_date: date
    running: bool
    sources: list[IngestionSourceStatus]
