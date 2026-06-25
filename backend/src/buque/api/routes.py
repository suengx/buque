from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from buque.api.deps import auth_router_dependencies
from buque.config import get_settings
from buque.db import get_db
from buque.models.entities import (
    DimSku,
    ErpSyncJob,
    FactAgentExplain,
    FactFeedback,
    FactMonitorResult,
    FeedbackDecision,
    HandlingStatus,
    MonitoringScope,
    RiskLevel,
    RiskType,
)
from buque.schemas.api import (
    AlertsMetaOut,
    DailyReportSummary,
    FeedbackCreate,
    FeedbackOut,
    FeedbackStats,
    MonitorResultOut,
    PaginatedAlerts,
    ReportAnalyticsOut,
    SkuDetailOut,
    TrendComparison,
    TrendPoint,
)
from buque.services.risk_aggregation import (
    business_scope_q,
    data_anomaly_count as count_data_anomalies,
    level_counts,
    sku_set_for_level,
    warehouse_scope_q,
)
from buque.services.snapshot_query import (
    get_snapshot,
    latest_snapshot_for_date,
    previous_snapshot,
    resolve_snapshot_id,
)

public_router = APIRouter(prefix="/api/v1")
router = APIRouter(prefix="/api/v1", dependencies=auth_router_dependencies())


def _explain_for(db: Session, snapshot_id: int, sku: str) -> FactAgentExplain | None:
    return (
        db.query(FactAgentExplain)
        .filter(FactAgentExplain.snapshot_id == snapshot_id, FactAgentExplain.sku == sku)
        .order_by(FactAgentExplain.id.desc())
        .first()
    )


def _result_to_out(result: FactMonitorResult, sku: DimSku | None, explain: FactAgentExplain | None) -> MonitorResultOut:
    return MonitorResultOut(
        id=result.id,
        date=result.date,
        sku=result.sku,
        product_name=sku.product_name if sku else None,
        warehouse=result.warehouse,
        channel=result.channel,
        scope=result.scope.value,
        risk_type=result.risk_type.value,
        risk_level=result.risk_level.value,
        trigger_rule=result.trigger_rule,
        trigger_metrics=result.trigger_metrics or {},
        dos=result.dos,
        ref_daily_sales=result.ref_daily_sales,
        available_inventory=result.available_inventory,
        inbound_relief_applied=result.inbound_relief_applied,
        relief_note=result.relief_note,
        handling_status=result.handling_status.value,
        primary_explanation=explain.primary_explanation if explain else None,
        suggested_action=explain.suggested_action if explain else None,
        responsible_role=explain.responsible_role if explain else None,
    )


def _count_new_skus(current: set[str], baseline: set[str]) -> int:
    return len([sku for sku in current if sku not in baseline])


def _build_trend_comparison(
    db: Session,
    current_sid: int,
    baseline_job: ErpSyncJob | None,
    *,
    baseline_label: str | None,
    available: bool = True,
) -> TrendComparison:
    current_red = sku_set_for_level(db, current_sid, RiskLevel.RED)
    current_orange = sku_set_for_level(db, current_sid, RiskLevel.ORANGE)
    if baseline_job is None:
        return TrendComparison(
            new_red_count=0,
            new_orange_count=0,
            baseline_label=baseline_label,
            baseline_snapshot_id=None,
            available=available,
        )
    prev_red = sku_set_for_level(db, baseline_job.id, RiskLevel.RED)
    prev_orange = sku_set_for_level(db, baseline_job.id, RiskLevel.ORANGE)
    return TrendComparison(
        new_red_count=_count_new_skus(current_red, prev_red),
        new_orange_count=_count_new_skus(current_orange, prev_orange),
        baseline_label=baseline_label,
        baseline_snapshot_id=baseline_job.id,
        available=available,
    )


def _format_snapshot_time(finished_at) -> str:
    if finished_at is None:
        return "—"
    tz = get_settings().tz
    return finished_at.astimezone(tz).strftime("%m/%d %H:%M")


@public_router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "buque"}


@router.get("/reports/daily", response_model=DailyReportSummary)
def daily_report(
    snapshot_id: int | None = None,
    db: Session = Depends(get_db),
) -> DailyReportSummary:
    sid = resolve_snapshot_id(db, snapshot_id)
    job = get_snapshot(db, sid)
    md = job.monitor_date
    prev = md - timedelta(days=1)

    base_q = business_scope_q(db, sid)
    monitored = (
        db.query(func.count(func.distinct(FactMonitorResult.sku)))
        .filter(
            FactMonitorResult.snapshot_id == sid,
            FactMonitorResult.scope == MonitoringScope.WAREHOUSE,
        )
        .scalar()
        or 0
    )

    def _count(level: RiskLevel, rtype: RiskType | None = None) -> int:
        q = base_q.filter(FactMonitorResult.risk_level == level)
        if rtype:
            q = q.filter(FactMonitorResult.risk_type == rtype)
        return q.count()

    prev_snapshot = latest_snapshot_for_date(db, prev)
    prev_day_label = f"昨日 {prev.isoformat()}"
    if prev_snapshot:
        prev_day_label = f"昨日快照 {_format_snapshot_time(prev_snapshot.finished_at)}"

    prev_chain = previous_snapshot(db, sid)
    prev_chain_label = (
        f"上序快照 {_format_snapshot_time(prev_chain.finished_at)}" if prev_chain else None
    )

    comparison_vs_prev_day = _build_trend_comparison(
        db,
        sid,
        prev_snapshot,
        baseline_label=prev_day_label,
        available=True,
    )
    comparison_vs_prev_snapshot = _build_trend_comparison(
        db,
        sid,
        prev_chain,
        baseline_label=prev_chain_label,
        available=prev_chain is not None,
    )

    stockout_hr = base_q.filter(
        FactMonitorResult.risk_type == RiskType.STOCKOUT,
        FactMonitorResult.risk_level.in_([RiskLevel.RED, RiskLevel.ORANGE]),
    ).count()
    slow_hr = base_q.filter(
        FactMonitorResult.risk_type == RiskType.SLOW_MOVING,
        FactMonitorResult.risk_level.in_([RiskLevel.RED, RiskLevel.ORANGE]),
    ).count()

    return DailyReportSummary(
        snapshot_id=sid,
        monitor_date=md,
        monitored_sku_count=monitored,
        new_red_count=comparison_vs_prev_day.new_red_count,
        new_orange_count=comparison_vs_prev_day.new_orange_count,
        comparison_vs_prev_day=comparison_vs_prev_day,
        comparison_vs_prev_snapshot=comparison_vs_prev_snapshot,
        stockout_high_risk_count=stockout_hr,
        slow_moving_high_risk_count=slow_hr,
        sales_anomaly_count=_count(RiskLevel.ORANGE, RiskType.SALES_ANOMALY)
        + _count(RiskLevel.YELLOW, RiskType.SALES_ANOMALY),
        data_anomaly_count=count_data_anomalies(db, sid),
        priority_today_count=base_q.filter(
            FactMonitorResult.risk_level == RiskLevel.RED,
            FactMonitorResult.requires_human_confirm.is_(True),
        ).count(),
    )


@router.get("/reports/analytics", response_model=ReportAnalyticsOut)
def report_analytics(
    snapshot_id: int | None = None,
    db: Session = Depends(get_db),
) -> ReportAnalyticsOut:
    sid = resolve_snapshot_id(db, snapshot_id)
    job = get_snapshot(db, sid)
    md = job.monitor_date

    base_q = business_scope_q(db, sid)

    level_counts_result = level_counts(db, sid)

    type_counts: dict[str, int] = {}
    for rtype, count in (
        base_q.with_entities(FactMonitorResult.risk_type, func.count())
        .group_by(FactMonitorResult.risk_type)
        .all()
    ):
        type_counts[rtype.value] = count

    trend_7d: list[TrendPoint] = []
    for offset in range(6, -1, -1):
        d = md - timedelta(days=offset)
        day_snapshot = latest_snapshot_for_date(db, d)
        counts = {level.value: 0 for level in RiskLevel}
        if day_snapshot:
            counts = level_counts(db, day_snapshot.id)
        trend_7d.append(
            TrendPoint(
                date=d,
                red=counts[RiskLevel.RED.value],
                orange=counts[RiskLevel.ORANGE.value],
                yellow=counts[RiskLevel.YELLOW.value],
                green=counts[RiskLevel.GREEN.value],
            )
        )

    priority_rows = (
        db.query(FactMonitorResult, DimSku)
        .outerjoin(DimSku, DimSku.sku == FactMonitorResult.sku)
        .filter(
            FactMonitorResult.snapshot_id == sid,
            FactMonitorResult.scope == MonitoringScope.WAREHOUSE,
            FactMonitorResult.risk_level == RiskLevel.RED,
            FactMonitorResult.requires_human_confirm.is_(True),
        )
        .order_by(FactMonitorResult.dos.asc())
        .limit(5)
        .all()
    )
    top_priority = [
        _result_to_out(result, sku, _explain_for(db, sid, result.sku))
        for result, sku in priority_rows
    ]

    return ReportAnalyticsOut(
        snapshot_id=sid,
        monitor_date=md,
        level_counts=level_counts_result,
        type_counts=type_counts,
        trend_7d=trend_7d,
        top_priority=top_priority,
    )


@router.get("/alerts/meta", response_model=AlertsMetaOut)
def alerts_meta(
    snapshot_id: int | None = None,
    db: Session = Depends(get_db),
) -> AlertsMetaOut:
    sid = resolve_snapshot_id(db, snapshot_id)
    job = get_snapshot(db, sid)
    scope_q = warehouse_scope_q(db, sid)
    warehouses = sorted(
        w for (w,) in scope_q.with_entities(FactMonitorResult.warehouse).distinct().all() if w
    )
    type_counts: dict[str, int] = {}
    for rtype, count in (
        scope_q.with_entities(FactMonitorResult.risk_type, func.count())
        .group_by(FactMonitorResult.risk_type)
        .all()
    ):
        type_counts[rtype.value] = count
    return AlertsMetaOut(
        snapshot_id=sid,
        monitor_date=job.monitor_date,
        warehouses=warehouses,
        type_counts=type_counts,
    )


@router.get("/alerts", response_model=PaginatedAlerts)
def list_alerts(
    snapshot_id: int | None = None,
    level: str | None = None,
    risk_type: str | None = None,
    warehouse: str | None = None,
    sku: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedAlerts:
    sid = resolve_snapshot_id(db, snapshot_id)
    q = (
        db.query(FactMonitorResult, DimSku)
        .outerjoin(DimSku, DimSku.sku == FactMonitorResult.sku)
        .filter(
            FactMonitorResult.snapshot_id == sid,
            FactMonitorResult.scope == MonitoringScope.WAREHOUSE,
        )
    )
    if level:
        q = q.filter(FactMonitorResult.risk_level == RiskLevel(level))
    if risk_type:
        q = q.filter(FactMonitorResult.risk_type == RiskType(risk_type))
    else:
        q = q.filter(FactMonitorResult.risk_type != RiskType.DATA_ANOMALY)
    if warehouse:
        q = q.filter(FactMonitorResult.warehouse == warehouse)
    if sku:
        q = q.filter(FactMonitorResult.sku.ilike(f"%{sku}%"))

    total = q.count()
    rows = (
        q.order_by(FactMonitorResult.risk_level.desc(), FactMonitorResult.dos.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items: list[MonitorResultOut] = []
    for result, sku_row in rows:
        explain = _explain_for(db, sid, result.sku)
        items.append(_result_to_out(result, sku_row, explain))

    return PaginatedAlerts(items=items, total=total, page=page, page_size=page_size)


@router.get("/alerts/{sku_id}", response_model=SkuDetailOut)
def sku_detail(
    sku_id: str,
    snapshot_id: int | None = None,
    warehouse: str | None = None,
    db: Session = Depends(get_db),
) -> SkuDetailOut:
    sid = resolve_snapshot_id(db, snapshot_id)
    job = get_snapshot(db, sid)
    q = db.query(FactMonitorResult).filter(
        FactMonitorResult.snapshot_id == sid,
        FactMonitorResult.sku == sku_id,
        FactMonitorResult.scope == MonitoringScope.WAREHOUSE,
    )
    if warehouse:
        q = q.filter(FactMonitorResult.warehouse == warehouse)
    result = q.order_by(FactMonitorResult.risk_level.desc()).first()
    if not result:
        raise HTTPException(status_code=404, detail="SKU 监控结果不存在")

    sku = db.get(DimSku, sku_id)
    explain = (
        db.query(FactAgentExplain)
        .filter(FactAgentExplain.snapshot_id == sid, FactAgentExplain.sku == sku_id)
        .order_by(FactAgentExplain.id.desc())
        .first()
    )
    return SkuDetailOut(
        snapshot_id=sid,
        monitor_date=job.monitor_date,
        sku=sku_id,
        product_name=sku.product_name if sku else None,
        warehouse=result.warehouse,
        risk_type=result.risk_type.value,
        risk_level=result.risk_level.value,
        trigger_rule=result.trigger_rule,
        trigger_metrics=result.trigger_metrics or {},
        dos=result.dos,
        ref_daily_sales=result.ref_daily_sales,
        available_inventory=result.available_inventory,
        primary_explanation=explain.primary_explanation if explain else None,
        secondary_explanation=explain.secondary_explanation if explain else None,
        tertiary_explanation=explain.tertiary_explanation if explain else None,
        explanation_tags=explain.explanation_tags if explain else [],
        key_evidence=explain.key_evidence if explain else [],
        suggested_action=explain.suggested_action if explain else None,
        responsible_role=explain.responsible_role if explain else None,
        action_deadline=explain.action_deadline if explain else None,
        require_human_confirm=explain.require_human_confirm if explain else False,
    )


@router.post("/feedback", response_model=FeedbackOut)
def create_feedback(payload: FeedbackCreate, db: Session = Depends(get_db)) -> FactFeedback:
    row = FactFeedback(
        date=payload.date,
        sku=payload.sku,
        risk_type=RiskType(payload.risk_type),
        agent_suggested_action=payload.agent_suggested_action,
        manual_conclusion=payload.manual_conclusion,
        decision=FeedbackDecision(payload.decision),
        reason_tag=payload.reason_tag,
        remark=payload.remark,
        handling_status=HandlingStatus.HANDLED,
    )
    db.add(row)
    if payload.snapshot_id is not None:
        db.query(FactMonitorResult).filter(
            FactMonitorResult.snapshot_id == payload.snapshot_id,
            FactMonitorResult.sku == payload.sku,
            FactMonitorResult.risk_type == RiskType(payload.risk_type),
        ).update({FactMonitorResult.handling_status: HandlingStatus.HANDLED})
    db.commit()
    db.refresh(row)
    return row


@router.get("/feedback/stats", response_model=FeedbackStats)
def feedback_stats(db: Session = Depends(get_db)) -> FeedbackStats:
    total = db.query(FactFeedback).count()
    adopted = db.query(FactFeedback).filter(FactFeedback.decision == FeedbackDecision.ADOPTED).count()
    rejected = db.query(FactFeedback).filter(FactFeedback.decision == FeedbackDecision.REJECTED).count()
    partial = db.query(FactFeedback).filter(FactFeedback.decision == FeedbackDecision.PARTIAL).count()
    rate = (adopted + partial * 0.5) / total if total else 0.0
    return FeedbackStats(
        total=total,
        adopted=adopted,
        rejected=rejected,
        partial=partial,
        adoption_rate=round(rate, 4),
    )


@router.get("/feedback", response_model=list[FeedbackOut])
def list_feedback(limit: int = 50, db: Session = Depends(get_db)) -> list[FactFeedback]:
    return db.query(FactFeedback).order_by(FactFeedback.created_at.desc()).limit(limit).all()
