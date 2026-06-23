from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class SkuBrief(BaseModel):
    sku: str
    product_name: str | None = None
    item_grade: str | None = None
    seasonality: str | None = None
    is_key_listing: bool = False


class TrendComparison(BaseModel):
    new_red_count: int
    new_orange_count: int
    baseline_label: str | None = None
    baseline_snapshot_id: int | None = None
    available: bool = True


class DailyReportSummary(BaseModel):
    snapshot_id: int
    monitor_date: date
    monitored_sku_count: int
    new_red_count: int
    new_orange_count: int
    comparison_vs_prev_day: TrendComparison
    comparison_vs_prev_snapshot: TrendComparison
    stockout_high_risk_count: int
    slow_moving_high_risk_count: int
    sales_anomaly_count: int
    data_anomaly_count: int
    priority_today_count: int


class TrendPoint(BaseModel):
    date: date
    red: int
    orange: int
    yellow: int
    green: int


class AlertsMetaOut(BaseModel):
    snapshot_id: int
    monitor_date: date
    warehouses: list[str]
    type_counts: dict[str, int]


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


class ReportAnalyticsOut(BaseModel):
    snapshot_id: int
    monitor_date: date
    level_counts: dict[str, int]
    type_counts: dict[str, int]
    trend_7d: list[TrendPoint]
    top_priority: list[MonitorResultOut]


class SkuDetailOut(BaseModel):
    snapshot_id: int
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


class AgentExplainOut(BaseModel):
    primary_explanation: str
    secondary_explanation: str | None = None
    tertiary_explanation: str | None = None
    explanation_tags: list[str] = []
    key_evidence: list[str] = []
    suggested_action: str
    responsible_role: str | None = None
    action_deadline: str | None = None
    require_human_confirm: bool = True
    confidence_note: str | None = None


class FeedbackCreate(BaseModel):
    snapshot_id: int | None = None
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
    snapshot_id: int
    monitor_date: date
    ingestion: dict[str, int]
    quality_issues: int
    monitor_results: int
    events: int
    explained: int


class PipelineRequest(BaseModel):
    monitor_date: date | None = None


class PipelineAccepted(BaseModel):
    snapshot_id: int
    monitor_date: date
    message: str = "同步并分析已启动"


class ErpSyncLogEntry(BaseModel):
    level: str
    message: str
    created_at: datetime


class IngestionSourceStatus(BaseModel):
    source: str
    status: str
    row_count: int
    file_path: str | None = None
    error: str | None = None
    finished_at: datetime | None = None
    ingestion_run_id: int | None = None


class PipelineStatusResponse(BaseModel):
    snapshot_id: int | None
    monitor_date: date
    running: bool
    job_status: str
    phase: str | None = None
    phase_message: str | None = None
    error: str | None = None
    finished_at: datetime | None = None
    sync_summary: dict | None = None
    analysis_summary: dict | None = None
    progress_current: int | None = None
    progress_total: int | None = None
    logs: list[ErpSyncLogEntry] = []
    sources: list[IngestionSourceStatus]


class SnapshotSummary(BaseModel):
    id: int
    monitor_date: date
    finished_at: datetime | None
    sync_summary: dict | None = None
    analysis_summary: dict | None = None


class OpsStatusResponse(BaseModel):
    timezone: str
    schedule_label: str
    next_scheduled_at: datetime
    pipeline_active: bool
    running_snapshot_id: int | None = None
    phase_message: str | None = None
    erp_configured: bool
