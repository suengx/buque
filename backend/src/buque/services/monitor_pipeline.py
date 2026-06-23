from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date

import httpx
from sqlalchemy.orm import Session

from buque.config import get_settings
from buque.models.entities import (
    ErpSyncPhase,
    EventPool,
    FactAgentExplain,
    FactMonitorResult,
    MonitoringScope,
    RiskLevel,
    RiskType,
)
from buque.rules.engine import MonitorFinding, RuleEngine
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
    def __init__(self, db: Session, monitor_date: date):
        self.db = db
        self.monitor_date = monitor_date

    def persist_findings(self, findings: list[MonitorFinding]) -> list[FactMonitorResult]:
        saved: list[FactMonitorResult] = []
        for f in findings:
            existing = (
                self.db.query(FactMonitorResult)
                .filter(
                    FactMonitorResult.date == self.monitor_date,
                    FactMonitorResult.sku == f.sku,
                    FactMonitorResult.warehouse == f.warehouse,
                    FactMonitorResult.scope == f.scope,
                    FactMonitorResult.risk_type == f.risk_type,
                )
                .first()
            )
            payload = dict(
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
            )
            if existing:
                for key, value in payload.items():
                    setattr(existing, key, value)
                row = existing
            else:
                row = FactMonitorResult(
                    date=self.monitor_date,
                    sku=f.sku,
                    warehouse=f.warehouse,
                    **payload,
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
        self.db.query(EventPool).filter(EventPool.date == self.monitor_date).delete()
        self.db.commit()
        events: list[EventPool] = []
        for r in results:
            if not r.requires_explanation:
                continue
            if r.risk_type == RiskType.DATA_ANOMALY:
                continue
            if r.scope != MonitoringScope.WAREHOUSE:
                continue
            event_id = f"{r.date.isoformat()}:{r.sku}:{r.warehouse}:{r.risk_type.value}"
            ev = EventPool(
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
    SYSTEM_PROMPT = """你是补雀 BuQue 库存监控解释 Agent。
根据触发指标输出 JSON，必须包含:
primary_explanation, secondary_explanation, tertiary_explanation,
explanation_tags (从给定标签库选择), key_evidence (数组),
suggested_action, responsible_role, action_deadline, require_human_confirm, confidence_note.
数据异常时不输出强业务结论。"""

    def __init__(self, db: Session):
        self.db = db

    def explain_events(
        self,
        monitor_date: date,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> int:
        events = self.db.query(EventPool).filter(EventPool.date == monitor_date).all()
        total = len(events)
        count = 0
        for event in events:
            if (
                self.db.query(FactAgentExplain)
                .filter(
                    FactAgentExplain.date == monitor_date,
                    FactAgentExplain.event_id == event.event_id,
                )
                .first()
            ):
                count += 1
                if on_progress:
                    on_progress(count, total)
                continue
            payload = self._explain_one(event)
            self.db.add(
                FactAgentExplain(
                    date=monitor_date,
                    sku=event.sku,
                    event_id=event.event_id,
                    primary_explanation=payload["primary_explanation"],
                    secondary_explanation=payload.get("secondary_explanation"),
                    tertiary_explanation=payload.get("tertiary_explanation"),
                    explanation_tags=payload.get("explanation_tags", []),
                    key_evidence=payload.get("key_evidence", []),
                    suggested_action=payload["suggested_action"],
                    responsible_role=payload.get("responsible_role", "计划主管"),
                    action_deadline=payload.get("action_deadline", "当天确认"),
                    require_human_confirm=payload.get("require_human_confirm", True),
                    confidence_note=payload.get("confidence_note"),
                    raw_response=payload,
                )
            )
            count += 1
            if on_progress:
                on_progress(count, total)
        self.db.commit()
        return count

    def _explain_one(self, event: EventPool) -> dict:
        if settings.llm_api_key and settings.llm_api_base:
            return self._call_llm(event)
        return self._rule_based(event)

    def _rule_based(self, event: EventPool) -> dict:
        metrics = event.trigger_metrics or {}
        relief = event.evidence_context.get("relief_note") if event.evidence_context else None
        if relief:
            return {
                "primary_explanation": "短期风险可控，需关注到货兑现",
                "secondary_explanation": "真实断货高风险",
                "tertiary_explanation": "在途延期导致风险抬升",
                "explanation_tags": ["短期风险可控，需关注到货兑现"],
                "key_evidence": [f"触发规则: {event.trigger_rule}", str(metrics)],
                "suggested_action": "跟踪到货兑现；延期则升回红灯",
                "responsible_role": "计划主管",
                "action_deadline": "当天确认",
                "require_human_confirm": True,
                "confidence_note": "规则解释（无 LLM）",
            }
        if event.risk_level == RiskLevel.RED:
            return {
                "primary_explanation": "真实断货高风险",
                "secondary_explanation": "需求超预期导致库存消耗加快",
                "tertiary_explanation": "运营放量导致",
                "explanation_tags": ["真实断货高风险"],
                "key_evidence": [f"DOS={metrics.get('dos')}", str(metrics)],
                "suggested_action": "确认销售计划并评估催交/调拨",
                "responsible_role": "计划主管",
                "action_deadline": "当天确认",
                "require_human_confirm": True,
                "confidence_note": "规则解释（无 LLM）",
            }
        return {
            "primary_explanation": "需进一步观察",
            "secondary_explanation": "数据异常待复核",
            "tertiary_explanation": None,
            "explanation_tags": ["数据异常待复核"],
            "key_evidence": [str(metrics)],
            "suggested_action": "人工复核",
            "responsible_role": "计划专员",
            "action_deadline": "3日内",
            "require_human_confirm": False,
            "confidence_note": "规则解释（无 LLM）",
        }

    def _call_llm(self, event: EventPool) -> dict:
        user_content = json.dumps(
            {
                "sku": event.sku,
                "warehouse": event.warehouse,
                "risk_type": event.risk_type.value,
                "risk_level": event.risk_level.value,
                "trigger_rule": event.trigger_rule,
                "trigger_metrics": event.trigger_metrics,
                "evidence_context": event.evidence_context,
                "allowed_tags": EXPLANATION_TAGS,
            },
            ensure_ascii=False,
        )
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
            return json.loads(content)


def run_rules(db: Session, monitor_date: date) -> list[FactMonitorResult]:
    cfg = RuleConfigService(db)
    findings = RuleEngine(db, monitor_date, cfg).run()
    return MonitorPersistence(db, monitor_date).persist_findings(findings)


def run_event_pool_and_explain(db: Session, monitor_date: date) -> tuple[int, int]:
    results = db.query(FactMonitorResult).filter(FactMonitorResult.date == monitor_date).all()
    events = MonitorPersistence(db, monitor_date).build_event_pool(results)
    explained = ExplainerAgent(db).explain_events(monitor_date)
    return len(events), explained


AnalysisProgressCallback = Callable[
    [ErpSyncPhase, str, int | None, int | None],
    None,
]


def run_analysis_pipeline(
    db: Session,
    monitor_date: date,
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
    issues = DataQualityChecker(db, monitor_date).run()

    report(ErpSyncPhase.RULES, "规则计算…")
    results = run_rules(db, monitor_date)

    report(ErpSyncPhase.EVENTS, "构建事件池…")
    events = MonitorPersistence(db, monitor_date).build_event_pool(results)
    event_count = len(events)

    def explain_progress(done: int, total: int) -> None:
        report(
            ErpSyncPhase.EXPLAIN,
            f"生成解释 {done}/{total}",
            done,
            total,
        )

    report(ErpSyncPhase.EXPLAIN, f"生成解释 0/{event_count}", 0, event_count)
    explained = ExplainerAgent(db).explain_events(monitor_date, on_progress=explain_progress)

    return {
        "quality_issues": len(issues),
        "monitor_results": len(results),
        "events": event_count,
        "explained": explained,
    }
