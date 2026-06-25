from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from buque.config import get_settings
from buque.models.entities import (
    DimSku,
    ErpSyncJob,
    FactInboundBatch,
    FactInventoryDaily,
    FactMonitorResult,
    FactSalesDaily,
    MonitoringScope,
    RiskLevel,
    RiskType,
)
from buque.services.explanation_engine import ExplanationRuleEngine
from buque.services.risk_aggregation import (
    business_scope_q,
    data_anomaly_count as count_data_anomalies,
    sku_set_for_level,
)
from buque.services.snapshot_query import (
    get_snapshot,
    latest_snapshot_for_date,
    previous_snapshot,
)

EXPLANATION_TAGS = [
    "运营放量导致",
    "促销刺激导致",
    "需求走弱风险",
    "供给受限导致表观销量下降",
    "真实断货高风险",
    "短期风险可控，需关注到货兑现",
    "去化持续弱",
    "计划补货偏多",
    "运营计划未同步到预测",
    "数据异常待复核",
]


FILTER_SCHEMA = {
    "levels": [level.value for level in RiskLevel],
    "risk_types": [rtype.value for rtype in RiskType],
}

_LEVEL_ALIASES: dict[str, RiskLevel] = {
    "RED": RiskLevel.RED,
    "red": RiskLevel.RED,
    "红色": RiskLevel.RED,
    "橙": RiskLevel.ORANGE,
    "ORANGE": RiskLevel.ORANGE,
    "orange": RiskLevel.ORANGE,
    "橙色": RiskLevel.ORANGE,
    "YELLOW": RiskLevel.YELLOW,
    "yellow": RiskLevel.YELLOW,
    "黄色": RiskLevel.YELLOW,
    "GREEN": RiskLevel.GREEN,
    "green": RiskLevel.GREEN,
    "绿色": RiskLevel.GREEN,
}

_RISK_TYPE_ALIASES: dict[str, RiskType] = {
    "STOCKOUT": RiskType.STOCKOUT,
    "stockout": RiskType.STOCKOUT,
    "断货": RiskType.STOCKOUT,
    "缺货": RiskType.STOCKOUT,
    "SLOW_MOVING": RiskType.SLOW_MOVING,
    "slow_moving": RiskType.SLOW_MOVING,
    "滞销": RiskType.SLOW_MOVING,
    "SALES_ANOMALY": RiskType.SALES_ANOMALY,
    "sales_anomaly": RiskType.SALES_ANOMALY,
    "销量异常": RiskType.SALES_ANOMALY,
    "FORECAST_BIAS": RiskType.FORECAST_BIAS,
    "forecast_bias": RiskType.FORECAST_BIAS,
    "预测偏差": RiskType.FORECAST_BIAS,
    "DATA_ANOMALY": RiskType.DATA_ANOMALY,
    "data_anomaly": RiskType.DATA_ANOMALY,
    "数据异常": RiskType.DATA_ANOMALY,
}


def normalize_risk_level(value: str | None) -> RiskLevel | None:
    if not value:
        return None
    key = value.strip()
    if key in _LEVEL_ALIASES:
        return _LEVEL_ALIASES[key]
    try:
        return RiskLevel(key.upper())
    except ValueError:
        return None


def normalize_risk_type(value: str | None) -> RiskType | None:
    if not value:
        return None
    key = value.strip()
    if key in _RISK_TYPE_ALIASES:
        return _RISK_TYPE_ALIASES[key]
    try:
        return RiskType(key.upper())
    except ValueError:
        return None


def _format_snapshot_time(finished_at) -> str:
    if finished_at is None:
        return "—"
    tz = get_settings().tz
    return finished_at.astimezone(tz).strftime("%m/%d %H:%M")


def _count_new_skus(current: set[str], baseline: set[str]) -> int:
    return len([sku for sku in current if sku not in baseline])


def _build_trend_comparison(
    db: Session,
    current_sid: int,
    baseline_job: ErpSyncJob | None,
    *,
    baseline_label: str | None,
    available: bool = True,
) -> dict[str, Any]:
    current_red = sku_set_for_level(db, current_sid, RiskLevel.RED)
    current_orange = sku_set_for_level(db, current_sid, RiskLevel.ORANGE)
    if baseline_job is None:
        return {
            "new_red_count": 0,
            "new_orange_count": 0,
            "baseline_label": baseline_label,
            "baseline_snapshot_id": None,
            "available": available,
        }
    prev_red = sku_set_for_level(db, baseline_job.id, RiskLevel.RED)
    prev_orange = sku_set_for_level(db, baseline_job.id, RiskLevel.ORANGE)
    return {
        "new_red_count": _count_new_skus(current_red, prev_red),
        "new_orange_count": _count_new_skus(current_orange, prev_orange),
        "baseline_label": baseline_label,
        "baseline_snapshot_id": baseline_job.id,
        "available": available,
    }


def fetch_daily_summary(db: Session, snapshot_id: int) -> dict[str, Any]:
    job = get_snapshot(db, snapshot_id)
    md = job.monitor_date
    prev = md - timedelta(days=1)
    sid = snapshot_id

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
        db, sid, prev_snapshot, baseline_label=prev_day_label, available=True
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

    return {
        "snapshot_id": sid,
        "monitor_date": md.isoformat(),
        "monitored_sku_count": monitored,
        "new_red_count": comparison_vs_prev_day["new_red_count"],
        "new_orange_count": comparison_vs_prev_day["new_orange_count"],
        "comparison_vs_prev_day": comparison_vs_prev_day,
        "comparison_vs_prev_snapshot": comparison_vs_prev_snapshot,
        "stockout_high_risk_count": stockout_hr,
        "slow_moving_high_risk_count": slow_hr,
        "sales_anomaly_count": _count(RiskLevel.ORANGE, RiskType.SALES_ANOMALY)
        + _count(RiskLevel.YELLOW, RiskType.SALES_ANOMALY),
        "data_anomaly_count": count_data_anomalies(db, sid),
        "priority_today_count": base_q.filter(
            FactMonitorResult.risk_level == RiskLevel.RED,
            FactMonitorResult.requires_human_confirm.is_(True),
        ).count(),
        "filter_schema": FILTER_SCHEMA,
    }


def fetch_alerts(
    db: Session,
    snapshot_id: int,
    *,
    level: str | None = None,
    risk_type: str | None = None,
    warehouse: str | None = None,
    sku: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    normalized_level = normalize_risk_level(level)
    if level and normalized_level is None:
        return {
            "error": f"无效的 level: {level}",
            "allowed_levels": FILTER_SCHEMA["levels"],
            "items": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
        }

    normalized_risk_type = normalize_risk_type(risk_type)
    if risk_type and normalized_risk_type is None:
        return {
            "error": f"无效的 risk_type: {risk_type}",
            "allowed_risk_types": FILTER_SCHEMA["risk_types"],
            "items": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
        }

    q = (
        db.query(FactMonitorResult, DimSku)
        .outerjoin(DimSku, DimSku.sku == FactMonitorResult.sku)
        .filter(
            FactMonitorResult.snapshot_id == snapshot_id,
            FactMonitorResult.scope == MonitoringScope.WAREHOUSE,
        )
    )
    if normalized_level:
        q = q.filter(FactMonitorResult.risk_level == normalized_level)
    if normalized_risk_type:
        q = q.filter(FactMonitorResult.risk_type == normalized_risk_type)
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

    items = []
    for result, sku_row in rows:
        items.append(
            {
                "id": result.id,
                "sku": result.sku,
                "product_name": sku_row.product_name if sku_row else None,
                "warehouse": result.warehouse,
                "risk_type": result.risk_type.value,
                "risk_level": result.risk_level.value,
                "trigger_rule": result.trigger_rule,
                "trigger_metrics": result.trigger_metrics or {},
                "dos": str(result.dos) if result.dos is not None else None,
                "ref_daily_sales": str(result.ref_daily_sales)
                if result.ref_daily_sales is not None
                else None,
                "available_inventory": result.available_inventory,
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "sort_hint": "risk_level desc, dos asc",
    }


def build_sku_context(
    db: Session,
    monitor_date: date,
    snapshot_id: int,
    sku: str,
    warehouse: str | None,
) -> dict[str, Any]:
    inv = (
        db.query(FactInventoryDaily)
        .filter(
            FactInventoryDaily.snapshot_id == snapshot_id,
            FactInventoryDaily.sku == sku,
        )
        .all()
    )
    if warehouse:
        inv = [r for r in inv if r.warehouse == warehouse]

    sales = (
        db.query(FactSalesDaily)
        .filter(
            FactSalesDaily.snapshot_id == snapshot_id,
            FactSalesDaily.sku == sku,
        )
        .limit(30)
        .all()
    )

    inbound_q = db.query(FactInboundBatch).filter(
        FactInboundBatch.snapshot_id == snapshot_id,
        FactInboundBatch.sku == sku,
    )
    if warehouse:
        inbound_q = inbound_q.filter(FactInboundBatch.warehouse == warehouse)
    inbound = inbound_q.all()

    monitor_q = db.query(FactMonitorResult).filter(
        FactMonitorResult.snapshot_id == snapshot_id,
        FactMonitorResult.sku == sku,
        FactMonitorResult.scope == MonitoringScope.WAREHOUSE,
    )
    if warehouse:
        monitor_q = monitor_q.filter(FactMonitorResult.warehouse == warehouse)
    monitor_rows = monitor_q.all()

    sku_meta = db.get(DimSku, sku)
    rule_engine = ExplanationRuleEngine()
    rule_explanations = [rule_engine.explain_result(r).as_dict() for r in monitor_rows]

    return {
        "monitor_date": monitor_date.isoformat(),
        "sku": sku,
        "warehouse": warehouse,
        "product_name": sku_meta.product_name if sku_meta else None,
        "inventory": [
            {
                "warehouse": r.warehouse,
                "available_inventory": r.available_inventory,
                "ref_daily_sales": float(r.ref_daily_sales) if r.ref_daily_sales else None,
                "dos": float(r.dos) if r.dos else None,
            }
            for r in inv
        ],
        "recent_sales_rows": len(sales),
        "inbound_batches": [
            {
                "warehouse": b.warehouse,
                "batch_id": b.batch_id,
                "unreceived_qty": b.unreceived_qty,
                "tms_status": b.tms_status,
                "eta": b.eta.isoformat() if b.eta else None,
                "eligible_for_relief": b.eligible_for_relief,
            }
            for b in inbound
        ],
        "monitor_results": [
            {
                "risk_type": r.risk_type.value,
                "risk_level": r.risk_level.value,
                "trigger_rule": r.trigger_rule,
                "trigger_metrics": r.trigger_metrics,
                "relief_note": r.relief_note,
            }
            for r in monitor_rows
        ],
        "rule_based_explanations": rule_explanations,
        "allowed_tags": EXPLANATION_TAGS,
    }


def dumps_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)
