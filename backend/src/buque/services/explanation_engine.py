"""解释规则引擎：按 docs/05 §5 规则表确定性生成主/次/第三解释，批量零 LLM。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from buque.models.entities import (
    EventPool,
    FactAgentExplain,
    FactMonitorResult,
    MonitoringScope,
    RiskLevel,
    RiskType,
)

CONFIDENCE_RULE = "规则解释"


@dataclass(frozen=True)
class ExplanationPayload:
    primary_explanation: str
    secondary_explanation: str | None
    tertiary_explanation: str | None
    explanation_tags: list[str]
    key_evidence: list[str]
    suggested_action: str
    responsible_role: str
    action_deadline: str
    require_human_confirm: bool
    confidence_note: str = CONFIDENCE_RULE

    def as_dict(self) -> dict[str, Any]:
        return {
            "primary_explanation": self.primary_explanation,
            "secondary_explanation": self.secondary_explanation,
            "tertiary_explanation": self.tertiary_explanation,
            "explanation_tags": self.explanation_tags,
            "key_evidence": self.key_evidence,
            "suggested_action": self.suggested_action,
            "responsible_role": self.responsible_role,
            "action_deadline": self.action_deadline,
            "require_human_confirm": self.require_human_confirm,
            "confidence_note": self.confidence_note,
        }


def event_id_for(
    monitor_date: date,
    sku: str,
    warehouse: str | None,
    risk_type: RiskType,
) -> str:
    return f"{monitor_date.isoformat()}:{sku}:{warehouse}:{risk_type.value}"


def qualifies_for_event_pool(result: FactMonitorResult) -> bool:
    if not result.requires_explanation:
        return False
    if result.risk_type == RiskType.DATA_ANOMALY:
        return False
    if result.scope != MonitoringScope.WAREHOUSE:
        return False
    if result.risk_level == RiskLevel.RED:
        return True
    if result.risk_level == RiskLevel.ORANGE and result.risk_type in {
        RiskType.STOCKOUT,
        RiskType.SLOW_MOVING,
    }:
        return True
    return False


def qualifies_for_rule_explanation(result: FactMonitorResult) -> bool:
    if result.scope != MonitoringScope.WAREHOUSE:
        return False
    if result.risk_type == RiskType.DATA_ANOMALY:
        return False
    if result.risk_level == RiskLevel.RED:
        return True
    if result.risk_level == RiskLevel.ORANGE and result.risk_type in {
        RiskType.STOCKOUT,
        RiskType.SLOW_MOVING,
    }:
        return result.requires_explanation
    return False


class ExplanationRuleEngine:
    """docs/05 典型解释规则 → 结构化解释 payload。"""

    def explain(
        self,
        *,
        risk_type: RiskType,
        risk_level: RiskLevel,
        trigger_rule: str,
        trigger_metrics: dict | None,
        relief_note: str | None = None,
        available_inventory: int | None = None,
        requires_human_confirm: bool = False,
    ) -> ExplanationPayload:
        metrics = trigger_metrics or {}
        evidence = [f"触发规则: {trigger_rule}", str(metrics)]

        if relief_note:
            return ExplanationPayload(
                primary_explanation="短期风险可控，需关注到货兑现",
                secondary_explanation="真实断货高风险",
                tertiary_explanation="在途延期导致风险抬升",
                explanation_tags=["短期风险可控，需关注到货兑现"],
                key_evidence=evidence,
                suggested_action="跟踪到货兑现；延期则升回红灯",
                responsible_role="计划主管",
                action_deadline="当天确认",
                require_human_confirm=True,
            )

        if trigger_rule == "SALES_SURGE":
            dos = metrics.get("dos")
            low_dos = dos is not None and float(dos) < float(metrics.get("threshold_red", 30))
            if low_dos:
                return ExplanationPayload(
                    primary_explanation="真实放量叠加断货风险抬升",
                    secondary_explanation="运营放量导致",
                    tertiary_explanation="促销刺激导致",
                    explanation_tags=["真实断货高风险", "运营放量导致"],
                    key_evidence=evidence,
                    suggested_action="先升级断货预警，再确认放量真实性",
                    responsible_role="计划主管",
                    action_deadline="当天确认",
                    require_human_confirm=requires_human_confirm,
                )
            return ExplanationPayload(
                primary_explanation="运营放量导致",
                secondary_explanation="促销刺激导致",
                tertiary_explanation=None,
                explanation_tags=["运营放量导致"],
                key_evidence=evidence,
                suggested_action="先与运营确认是否为计划内放量",
                responsible_role="运营主管",
                action_deadline="3日内",
                require_human_confirm=False,
            )

        if trigger_rule == "SALES_DROP":
            low_available = available_inventory is not None and available_inventory <= 0
            if low_available:
                return ExplanationPayload(
                    primary_explanation="供给受限导致表观销量下降",
                    secondary_explanation="需求走弱风险",
                    tertiary_explanation=None,
                    explanation_tags=["供给受限导致表观销量下降"],
                    key_evidence=evidence,
                    suggested_action="先排除供给限制，不直接下调需求",
                    responsible_role="计划主管",
                    action_deadline="3日内",
                    require_human_confirm=False,
                )
            return ExplanationPayload(
                primary_explanation="需求走弱风险",
                secondary_explanation="运营收量导致",
                tertiary_explanation=None,
                explanation_tags=["需求走弱风险"],
                key_evidence=evidence,
                suggested_action="提醒运营确认流量、转化、价格变化",
                responsible_role="运营主管",
                action_deadline="3日内",
                require_human_confirm=False,
            )

        if risk_type == RiskType.SLOW_MOVING or trigger_rule == "DOS_SLOW_MOVING":
            return ExplanationPayload(
                primary_explanation="去化持续弱",
                secondary_explanation="计划补货偏多",
                tertiary_explanation=None,
                explanation_tags=["去化持续弱"],
                key_evidence=evidence,
                suggested_action="降低后续补货节奏，并同步运营评估去化动作",
                responsible_role="计划主管",
                action_deadline="3日内",
                require_human_confirm=requires_human_confirm,
            )

        if risk_type == RiskType.STOCKOUT or trigger_rule == "DOS_STOCKOUT":
            return ExplanationPayload(
                primary_explanation="真实断货高风险",
                secondary_explanation="在途延期导致风险抬升",
                tertiary_explanation="运营放量导致",
                explanation_tags=["真实断货高风险"],
                key_evidence=evidence,
                suggested_action="计划主管与运营主管确认催交 / 采购 / 控量",
                responsible_role="计划主管",
                action_deadline="当天确认",
                require_human_confirm=requires_human_confirm or risk_level == RiskLevel.RED,
            )

        if risk_type == RiskType.DATA_ANOMALY or trigger_rule == "MISSING_DATA_BLOCK":
            return ExplanationPayload(
                primary_explanation="销量数据缺失或延迟",
                secondary_explanation="库存数据口径异常",
                tertiary_explanation=None,
                explanation_tags=["数据异常待复核"],
                key_evidence=evidence,
                suggested_action="先修复数据，再重新生成判断",
                responsible_role="计划专员",
                action_deadline="当天确认",
                require_human_confirm=False,
            )

        return ExplanationPayload(
            primary_explanation="需进一步观察",
            secondary_explanation="数据异常待复核",
            tertiary_explanation=None,
            explanation_tags=["数据异常待复核"],
            key_evidence=evidence,
            suggested_action="人工复核",
            responsible_role="计划专员",
            action_deadline="3日内",
            require_human_confirm=False,
        )

    def explain_event(self, event: EventPool) -> ExplanationPayload:
        relief = None
        if event.evidence_context:
            relief = event.evidence_context.get("relief_note")
            available = event.evidence_context.get("available_inventory")
        else:
            available = None
        return self.explain(
            risk_type=event.risk_type,
            risk_level=event.risk_level,
            trigger_rule=event.trigger_rule,
            trigger_metrics=event.trigger_metrics,
            relief_note=relief,
            available_inventory=available,
            requires_human_confirm=event.require_human_confirm,
        )

    def explain_result(self, result: FactMonitorResult) -> ExplanationPayload:
        return self.explain(
            risk_type=result.risk_type,
            risk_level=result.risk_level,
            trigger_rule=result.trigger_rule,
            trigger_metrics=result.trigger_metrics,
            relief_note=result.relief_note,
            available_inventory=result.available_inventory,
            requires_human_confirm=result.requires_human_confirm,
        )


def persist_rule_explanations(
    db: Session,
    monitor_date: date,
    on_progress: Callable[[int, int], None] | None = None,
) -> int:
    """为符合条件的监控结果批量写入 fact_agent_explain（规则引擎，无 LLM）。"""
    engine = ExplanationRuleEngine()
    results = (
        db.query(FactMonitorResult)
        .filter(
            FactMonitorResult.date == monitor_date,
            FactMonitorResult.scope == MonitoringScope.WAREHOUSE,
        )
        .all()
    )
    targets = [r for r in results if qualifies_for_rule_explanation(r)]
    total = len(targets)
    count = 0
    for result in targets:
        eid = event_id_for(monitor_date, result.sku, result.warehouse, result.risk_type)
        payload = engine.explain_result(result)
        existing = (
            db.query(FactAgentExplain)
            .filter(
                FactAgentExplain.date == monitor_date,
                FactAgentExplain.event_id == eid,
            )
            .first()
        )
        data = payload.as_dict()
        if existing:
            existing.primary_explanation = data["primary_explanation"]
            existing.secondary_explanation = data.get("secondary_explanation")
            existing.tertiary_explanation = data.get("tertiary_explanation")
            existing.explanation_tags = data.get("explanation_tags", [])
            existing.key_evidence = data.get("key_evidence", [])
            existing.suggested_action = data["suggested_action"]
            existing.responsible_role = data["responsible_role"]
            existing.action_deadline = data.get("action_deadline")
            existing.require_human_confirm = data.get("require_human_confirm", True)
            existing.confidence_note = data.get("confidence_note")
            existing.raw_response = data
        else:
            db.add(
                FactAgentExplain(
                    date=monitor_date,
                    sku=result.sku,
                    event_id=eid,
                    **data,
                    raw_response=data,
                )
            )
        count += 1
        if on_progress:
            on_progress(count, total)
    db.commit()
    return count
