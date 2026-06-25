"""业务风险聚合：数据异常不参与红橙黄绿统计。"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Query, Session

from buque.models.entities import FactMonitorResult, MonitoringScope, RiskLevel, RiskType


def warehouse_scope_q(db: Session, snapshot_id: int) -> Query:
    return db.query(FactMonitorResult).filter(
        FactMonitorResult.snapshot_id == snapshot_id,
        FactMonitorResult.scope == MonitoringScope.WAREHOUSE,
    )


def business_scope_q(db: Session, snapshot_id: int) -> Query:
    return warehouse_scope_q(db, snapshot_id).filter(
        FactMonitorResult.risk_type != RiskType.DATA_ANOMALY,
    )


def data_anomaly_scope_q(db: Session, snapshot_id: int) -> Query:
    return warehouse_scope_q(db, snapshot_id).filter(
        FactMonitorResult.risk_type == RiskType.DATA_ANOMALY,
    )


def level_counts(db: Session, snapshot_id: int) -> dict[str, int]:
    counts = {level.value: 0 for level in RiskLevel}
    for level, count in (
        business_scope_q(db, snapshot_id)
        .with_entities(FactMonitorResult.risk_level, func.count())
        .group_by(FactMonitorResult.risk_level)
        .all()
    ):
        counts[level.value] = count
    return counts


def sku_set_for_level(db: Session, snapshot_id: int, level: RiskLevel) -> set[str]:
    return {
        r.sku
        for r in business_scope_q(db, snapshot_id)
        .filter(FactMonitorResult.risk_level == level)
        .all()
    }


def data_anomaly_count(db: Session, snapshot_id: int) -> int:
    return data_anomaly_scope_q(db, snapshot_id).count()
