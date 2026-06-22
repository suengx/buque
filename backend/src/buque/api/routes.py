from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from buque.db import get_db
from buque.models.entities import (
    DimSku,
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
    DailyReportSummary,
    FeedbackCreate,
    FeedbackOut,
    FeedbackStats,
    MonitorResultOut,
    PaginatedAlerts,
    PipelineRunResult,
    SkuDetailOut,
)

router = APIRouter(prefix="/api/v1")


def _latest_monitor_date(db: Session) -> date | None:
    return db.query(func.max(FactMonitorResult.date)).scalar()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "buque"}


@router.get("/reports/daily", response_model=DailyReportSummary)
def daily_report(
    monitor_date: date | None = None,
    db: Session = Depends(get_db),
) -> DailyReportSummary:
    md = monitor_date or _latest_monitor_date(db) or date.today()
    prev = md - timedelta(days=1)

    base_q = db.query(FactMonitorResult).filter(
        FactMonitorResult.date == md,
        FactMonitorResult.scope == MonitoringScope.WAREHOUSE,
    )
    monitored = db.query(func.count(func.distinct(FactMonitorResult.sku))).filter(
        FactMonitorResult.date == md
    ).scalar() or 0

    def _count(level: RiskLevel, rtype: RiskType | None = None) -> int:
        q = base_q.filter(FactMonitorResult.risk_level == level)
        if rtype:
            q = q.filter(FactMonitorResult.risk_type == rtype)
        return q.count()

    prev_red = set(
        r.sku
        for r in db.query(FactMonitorResult)
        .filter(
            FactMonitorResult.date == prev,
            FactMonitorResult.risk_level == RiskLevel.RED,
            FactMonitorResult.scope == MonitoringScope.WAREHOUSE,
        )
        .all()
    )
    today_red = [
        r.sku
        for r in base_q.filter(FactMonitorResult.risk_level == RiskLevel.RED).all()
    ]
    new_red = len([s for s in today_red if s not in prev_red])

    prev_orange = set(
        r.sku
        for r in db.query(FactMonitorResult)
        .filter(
            FactMonitorResult.date == prev,
            FactMonitorResult.risk_level == RiskLevel.ORANGE,
            FactMonitorResult.scope == MonitoringScope.WAREHOUSE,
        )
        .all()
    )
    today_orange = [
        r.sku
        for r in base_q.filter(FactMonitorResult.risk_level == RiskLevel.ORANGE).all()
    ]
    new_orange = len([s for s in today_orange if s not in prev_orange])

    stockout_hr = base_q.filter(
        FactMonitorResult.risk_type == RiskType.STOCKOUT,
        FactMonitorResult.risk_level.in_([RiskLevel.RED, RiskLevel.ORANGE]),
    ).count()
    slow_hr = base_q.filter(
        FactMonitorResult.risk_type == RiskType.SLOW_MOVING,
        FactMonitorResult.risk_level.in_([RiskLevel.RED, RiskLevel.ORANGE]),
    ).count()

    return DailyReportSummary(
        monitor_date=md,
        monitored_sku_count=monitored,
        new_red_count=new_red,
        new_orange_count=new_orange,
        stockout_high_risk_count=stockout_hr,
        slow_moving_high_risk_count=slow_hr,
        sales_anomaly_count=_count(RiskLevel.ORANGE, RiskType.SALES_ANOMALY)
        + _count(RiskLevel.YELLOW, RiskType.SALES_ANOMALY),
        data_anomaly_count=_count(RiskLevel.ORANGE, RiskType.DATA_ANOMALY),
        priority_today_count=base_q.filter(
            FactMonitorResult.risk_level == RiskLevel.RED,
            FactMonitorResult.requires_human_confirm.is_(True),
        ).count(),
    )


@router.get("/alerts", response_model=PaginatedAlerts)
def list_alerts(
    monitor_date: date | None = None,
    level: str | None = None,
    risk_type: str | None = None,
    warehouse: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedAlerts:
    md = monitor_date or _latest_monitor_date(db) or date.today()
    q = (
        db.query(FactMonitorResult, DimSku)
        .outerjoin(DimSku, DimSku.sku == FactMonitorResult.sku)
        .filter(
            FactMonitorResult.date == md,
            FactMonitorResult.scope == MonitoringScope.WAREHOUSE,
        )
    )
    if level:
        q = q.filter(FactMonitorResult.risk_level == RiskLevel(level))
    if risk_type:
        q = q.filter(FactMonitorResult.risk_type == RiskType(risk_type))
    if warehouse:
        q = q.filter(FactMonitorResult.warehouse == warehouse)

    total = q.count()
    rows = (
        q.order_by(FactMonitorResult.risk_level.desc(), FactMonitorResult.dos.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items: list[MonitorResultOut] = []
    for result, sku in rows:
        explain = (
            db.query(FactAgentExplain)
            .filter(
                FactAgentExplain.date == md,
                FactAgentExplain.sku == result.sku,
            )
            .order_by(FactAgentExplain.id.desc())
            .first()
        )
        items.append(
            MonitorResultOut(
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
        )

    return PaginatedAlerts(items=items, total=total, page=page, page_size=page_size)


@router.get("/alerts/{sku_id}", response_model=SkuDetailOut)
def sku_detail(
    sku_id: str,
    monitor_date: date | None = None,
    warehouse: str | None = None,
    db: Session = Depends(get_db),
) -> SkuDetailOut:
    md = monitor_date or _latest_monitor_date(db) or date.today()
    q = db.query(FactMonitorResult).filter(
        FactMonitorResult.date == md,
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
        .filter(FactAgentExplain.date == md, FactAgentExplain.sku == sku_id)
        .order_by(FactAgentExplain.id.desc())
        .first()
    )
    return SkuDetailOut(
        monitor_date=md,
        sku=sku_id,
        product_name=sku.product_name if sku else None,
        warehouse=result.warehouse,
        risk_type=result.risk_type.value,
        risk_level=result.risk_level.value,
        trigger_metrics=result.trigger_metrics or {},
        dos=result.dos,
        primary_explanation=explain.primary_explanation if explain else None,
        secondary_explanation=explain.secondary_explanation if explain else None,
        tertiary_explanation=explain.tertiary_explanation if explain else None,
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
    db.query(FactMonitorResult).filter(
        FactMonitorResult.date == payload.date,
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
