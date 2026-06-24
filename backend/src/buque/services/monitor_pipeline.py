from __future__ import annotations

from collections.abc import Callable
from datetime import date

from sqlalchemy.orm import Session

from buque.models.entities import (
    ErpSyncPhase,
    EventPool,
    FactMonitorResult,
    MonitoringScope,
)
from buque.rules.engine import MonitorFinding, RuleEngine
from buque.services.explanation_engine import (
    event_id_for,
    persist_rule_explanations,
    qualifies_for_event_pool,
)
from buque.services.rule_config import RuleConfigService


class MonitorPersistence:
    def __init__(self, db: Session, monitor_date: date, snapshot_id: int):
        self.db = db
        self.monitor_date = monitor_date
        self.snapshot_id = snapshot_id

    def persist_findings(self, findings: list[MonitorFinding]) -> list[FactMonitorResult]:
        saved: list[FactMonitorResult] = []
        for f in findings:
            row = FactMonitorResult(
                snapshot_id=self.snapshot_id,
                date=self.monitor_date,
                sku=f.sku,
                warehouse=f.warehouse,
                channel=f.channel,
                risk_level=f.risk_level,
                trigger_rule=f.trigger_rule,
                trigger_metrics=f.trigger_metrics,
                dos=f.dos,
                ref_daily_sales=f.ref_daily_sales,
                available_inventory=f.available_inventory,
                inbound_relief_applied=f.inbound_relief_applied,
                relief_note=f.relief_note,
                requires_explanation=f.requires_explanation,
                requires_human_confirm=f.requires_human_confirm,
                scope=f.scope,
                risk_type=f.risk_type,
            )
            self.db.add(row)
            saved.append(row)
        self.db.commit()
        for row in saved:
            self.db.refresh(row)
        return saved

    def build_event_pool(self, results: list[FactMonitorResult]) -> list[EventPool]:
        events: list[EventPool] = []
        for r in results:
            if not qualifies_for_event_pool(r):
                continue
            event_id = event_id_for(
                self.snapshot_id, self.monitor_date, r.sku, r.warehouse, r.risk_type
            )
            ev = EventPool(
                snapshot_id=self.snapshot_id,
                event_id=event_id,
                date=r.date,
                sku=r.sku,
                warehouse=r.warehouse,
                risk_type=r.risk_type,
                risk_level=r.risk_level,
                trigger_rule=r.trigger_rule,
                trigger_metrics=r.trigger_metrics,
                evidence_context={
                    "dos": float(r.dos) if r.dos else None,
                    "ref_daily_sales": float(r.ref_daily_sales) if r.ref_daily_sales else None,
                    "available_inventory": r.available_inventory,
                    "relief_note": r.relief_note,
                },
                require_human_confirm=r.requires_human_confirm,
                monitor_result_id=r.id,
            )
            self.db.add(ev)
            events.append(ev)
        self.db.commit()
        return events


def run_rules(db: Session, monitor_date: date, snapshot_id: int) -> list[FactMonitorResult]:
    cfg = RuleConfigService(db)
    findings = RuleEngine(db, monitor_date, snapshot_id, cfg).run()
    return MonitorPersistence(db, monitor_date, snapshot_id).persist_findings(findings)


def run_event_pool_and_explain(
    db: Session, monitor_date: date, snapshot_id: int
) -> tuple[int, int]:
    results = (
        db.query(FactMonitorResult)
        .filter(FactMonitorResult.snapshot_id == snapshot_id)
        .all()
    )
    events = MonitorPersistence(db, monitor_date, snapshot_id).build_event_pool(results)
    explained = persist_rule_explanations(db, monitor_date, snapshot_id)
    return len(events), explained


AnalysisProgressCallback = Callable[
    [ErpSyncPhase, str, int | None, int | None],
    None,
]


def run_analysis_pipeline(
    db: Session,
    monitor_date: date,
    snapshot_id: int,
    on_progress: AnalysisProgressCallback | None = None,
) -> dict[str, int]:
    from buque.quality.checker import DataQualityChecker

    def report(
        phase: ErpSyncPhase,
        message: str,
        current: int | None = None,
        total: int | None = None,
    ) -> None:
        if on_progress:
            on_progress(phase, message, current, total)

    report(ErpSyncPhase.QUALITY, "数据质量检查…")
    issues = DataQualityChecker(db, monitor_date, snapshot_id).run()

    report(ErpSyncPhase.RULES, "规则计算…")
    results = run_rules(db, monitor_date, snapshot_id)

    report(ErpSyncPhase.EVENTS, "构建事件池…")
    events = MonitorPersistence(db, monitor_date, snapshot_id).build_event_pool(results)
    event_count = len(events)

    def explain_progress(done: int, total: int) -> None:
        report(
            ErpSyncPhase.EXPLAIN,
            f"应用解释规则 {done}/{total}",
            done,
            total,
        )

    report(ErpSyncPhase.EXPLAIN, "应用解释规则…", 0, event_count)
    explained = persist_rule_explanations(
        db, monitor_date, snapshot_id, on_progress=explain_progress
    )

    return {
        "quality_issues": len(issues),
        "monitor_results": len(results),
        "events": event_count,
        "explained": explained,
    }
