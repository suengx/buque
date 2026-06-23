from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date

import httpx
from sqlalchemy.orm import Session

from buque.config import get_settings
from buque.models.entities import (
    DimSku,
    ErpSyncPhase,
    EventPool,
    FactAgentExplain,
    FactInboundBatch,
    FactInventoryDaily,
    FactMonitorResult,
    FactSalesDaily,
    MonitoringScope,
)
from buque.rules.engine import MonitorFinding, RuleEngine
from buque.services.explanation_engine import (
    ExplanationRuleEngine,
    event_id_for,
    persist_rule_explanations,
    qualifies_for_event_pool,
)
from buque.services.rule_config import RuleConfigService

settings = get_settings()

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


class ExplainerAgent:
    """按需 Agent：拉取 SKU 上下文后单次 LLM 深度分析（批量分析不调用）。"""

    SYSTEM_PROMPT = """你是补雀 BuQue 库存监控解释 Agent。
根据提供的 SKU 事实数据输出 JSON，必须包含:
primary_explanation, secondary_explanation, tertiary_explanation,
explanation_tags (从给定标签库选择), key_evidence (数组),
suggested_action, responsible_role, action_deadline, require_human_confirm, confidence_note.
数据异常时不输出强业务结论。结合库存、销量、在途与已有规则结论给出可执行建议。"""

    def __init__(self, db: Session):
        self.db = db

    def build_sku_context(
        self,
        monitor_date: date,
        snapshot_id: int,
        sku: str,
        warehouse: str | None,
    ) -> dict:
        inv = (
            self.db.query(FactInventoryDaily)
            .filter(
                FactInventoryDaily.snapshot_id == snapshot_id,
                FactInventoryDaily.sku == sku,
            )
            .all()
        )
        if warehouse:
            inv = [r for r in inv if r.warehouse == warehouse]

        sales = (
            self.db.query(FactSalesDaily)
            .filter(
                FactSalesDaily.snapshot_id == snapshot_id,
                FactSalesDaily.sku == sku,
            )
            .limit(30)
            .all()
        )

        inbound_q = self.db.query(FactInboundBatch).filter(
            FactInboundBatch.snapshot_id == snapshot_id,
            FactInboundBatch.sku == sku,
        )
        if warehouse:
            inbound_q = inbound_q.filter(FactInboundBatch.warehouse == warehouse)
        inbound = inbound_q.all()

        monitor_q = self.db.query(FactMonitorResult).filter(
            FactMonitorResult.snapshot_id == snapshot_id,
            FactMonitorResult.sku == sku,
            FactMonitorResult.scope == MonitoringScope.WAREHOUSE,
        )
        if warehouse:
            monitor_q = monitor_q.filter(FactMonitorResult.warehouse == warehouse)
        monitor_rows = monitor_q.all()

        sku_meta = self.db.get(DimSku, sku)
        rule_engine = ExplanationRuleEngine()
        rule_explanations = [
            rule_engine.explain_result(r).as_dict() for r in monitor_rows
        ]

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

    def explain_sku_on_demand(
        self,
        monitor_date: date,
        snapshot_id: int,
        sku: str,
        warehouse: str | None,
    ) -> dict:
        if settings.llm_explain_mode == "off" or not settings.llm_api_key or not settings.llm_api_base:
            monitor_q = self.db.query(FactMonitorResult).filter(
                FactMonitorResult.snapshot_id == snapshot_id,
                FactMonitorResult.sku == sku,
                FactMonitorResult.scope == MonitoringScope.WAREHOUSE,
            )
            if warehouse:
                monitor_q = monitor_q.filter(FactMonitorResult.warehouse == warehouse)
            result = monitor_q.order_by(FactMonitorResult.risk_level.desc()).first()
            if not result:
                raise ValueError("无监控结果")
            payload = ExplanationRuleEngine().explain_result(result).as_dict()
            payload["confidence_note"] = "规则解释（LLM 未启用）"
            return payload

        context = self.build_sku_context(monitor_date, snapshot_id, sku, warehouse)
        user_content = json.dumps(context, ensure_ascii=False)
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{settings.llm_api_base.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={
                    "model": settings.llm_model,
                    "messages": [
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            payload = json.loads(content)
            payload["confidence_note"] = payload.get("confidence_note") or "Agent 深度分析"

        monitor_q = self.db.query(FactMonitorResult).filter(
            FactMonitorResult.snapshot_id == snapshot_id,
            FactMonitorResult.sku == sku,
            FactMonitorResult.scope == MonitoringScope.WAREHOUSE,
        )
        if warehouse:
            monitor_q = monitor_q.filter(FactMonitorResult.warehouse == warehouse)
        result = monitor_q.order_by(FactMonitorResult.risk_level.desc()).first()
        if result:
            eid = event_id_for(snapshot_id, monitor_date, sku, result.warehouse, result.risk_type)
            existing = (
                self.db.query(FactAgentExplain)
                .filter(
                    FactAgentExplain.snapshot_id == snapshot_id,
                    FactAgentExplain.event_id == eid,
                )
                .first()
            )
            fields = {
                "primary_explanation": payload["primary_explanation"],
                "secondary_explanation": payload.get("secondary_explanation"),
                "tertiary_explanation": payload.get("tertiary_explanation"),
                "explanation_tags": payload.get("explanation_tags", []),
                "key_evidence": payload.get("key_evidence", []),
                "suggested_action": payload["suggested_action"],
                "responsible_role": payload.get("responsible_role", "计划主管"),
                "action_deadline": payload.get("action_deadline", "当天确认"),
                "require_human_confirm": payload.get("require_human_confirm", True),
                "confidence_note": payload.get("confidence_note"),
                "raw_response": payload,
            }
            if existing:
                for k, v in fields.items():
                    setattr(existing, k, v)
            else:
                self.db.add(
                    FactAgentExplain(
                        snapshot_id=snapshot_id,
                        date=monitor_date,
                        sku=sku,
                        event_id=eid,
                        **fields,
                    )
                )
            self.db.commit()
        return payload


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
