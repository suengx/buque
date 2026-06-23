"""解释规则引擎单测：覆盖 docs/05 §5 典型规则行。"""

from datetime import date
from unittest.mock import MagicMock

import pytest

from buque.models.entities import MonitoringScope, RiskLevel, RiskType
from buque.services.explanation_engine import (
    ExplanationRuleEngine,
    qualifies_for_event_pool,
    qualifies_for_rule_explanation,
)


@pytest.fixture
def engine() -> ExplanationRuleEngine:
    return ExplanationRuleEngine()


def test_sales_surge_primary(engine: ExplanationRuleEngine) -> None:
    payload = engine.explain(
        risk_type=RiskType.SALES_ANOMALY,
        risk_level=RiskLevel.ORANGE,
        trigger_rule="SALES_SURGE",
        trigger_metrics={"dos": 45, "threshold_red": 30},
    )
    assert payload.primary_explanation == "运营放量导致"
    assert payload.secondary_explanation == "促销刺激导致"


def test_sales_surge_with_low_dos(engine: ExplanationRuleEngine) -> None:
    payload = engine.explain(
        risk_type=RiskType.SALES_ANOMALY,
        risk_level=RiskLevel.RED,
        trigger_rule="SALES_SURGE",
        trigger_metrics={"dos": 20, "threshold_red": 30},
    )
    assert payload.primary_explanation == "真实放量叠加断货风险抬升"
    assert "运营放量导致" in payload.explanation_tags


def test_sales_drop_demand_weak(engine: ExplanationRuleEngine) -> None:
    payload = engine.explain(
        risk_type=RiskType.SALES_ANOMALY,
        risk_level=RiskLevel.ORANGE,
        trigger_rule="SALES_DROP",
        trigger_metrics={},
        available_inventory=100,
    )
    assert payload.primary_explanation == "需求走弱风险"
    assert payload.suggested_action == "提醒运营确认流量、转化、价格变化"


def test_sales_drop_supply_limited(engine: ExplanationRuleEngine) -> None:
    payload = engine.explain(
        risk_type=RiskType.SALES_ANOMALY,
        risk_level=RiskLevel.ORANGE,
        trigger_rule="SALES_DROP",
        trigger_metrics={},
        available_inventory=0,
    )
    assert payload.primary_explanation == "供给受限导致表观销量下降"


def test_low_dos_stockout(engine: ExplanationRuleEngine) -> None:
    payload = engine.explain(
        risk_type=RiskType.STOCKOUT,
        risk_level=RiskLevel.RED,
        trigger_rule="DOS_STOCKOUT",
        trigger_metrics={"dos": 12},
        requires_human_confirm=True,
    )
    assert payload.primary_explanation == "真实断货高风险"
    assert payload.require_human_confirm is True


def test_inbound_relief(engine: ExplanationRuleEngine) -> None:
    payload = engine.explain(
        risk_type=RiskType.STOCKOUT,
        risk_level=RiskLevel.ORANGE,
        trigger_rule="DOS_STOCKOUT",
        trigger_metrics={"dos": 25},
        relief_note="ETA 安全窗口内可覆盖",
    )
    assert payload.primary_explanation == "短期风险可控，需关注到货兑现"
    assert payload.suggested_action == "跟踪到货兑现；延期则升回红灯"


def test_slow_moving(engine: ExplanationRuleEngine) -> None:
    payload = engine.explain(
        risk_type=RiskType.SLOW_MOVING,
        risk_level=RiskLevel.RED,
        trigger_rule="DOS_SLOW_MOVING",
        trigger_metrics={"dos": 180},
    )
    assert payload.primary_explanation == "去化持续弱"
    assert payload.secondary_explanation == "计划补货偏多"


def test_data_anomaly(engine: ExplanationRuleEngine) -> None:
    payload = engine.explain(
        risk_type=RiskType.DATA_ANOMALY,
        risk_level=RiskLevel.ORANGE,
        trigger_rule="MISSING_DATA_BLOCK",
        trigger_metrics={},
    )
    assert payload.primary_explanation == "销量数据缺失或延迟"
    assert "数据异常待复核" in payload.explanation_tags


def test_qualifies_for_event_pool_red_only_orange_stockout() -> None:
    md = date(2026, 6, 22)

    def make_row(**kwargs):
        row = MagicMock()
        row.requires_explanation = kwargs.get("requires_explanation", True)
        row.risk_type = kwargs.get("risk_type", RiskType.STOCKOUT)
        row.scope = kwargs.get("scope", MonitoringScope.WAREHOUSE)
        row.risk_level = kwargs.get("risk_level", RiskLevel.RED)
        row.date = md
        return row

    assert qualifies_for_event_pool(make_row(risk_level=RiskLevel.RED)) is True
    assert (
        qualifies_for_event_pool(
            make_row(risk_level=RiskLevel.ORANGE, risk_type=RiskType.STOCKOUT)
        )
        is True
    )
    assert (
        qualifies_for_event_pool(
            make_row(risk_level=RiskLevel.ORANGE, risk_type=RiskType.SALES_ANOMALY)
        )
        is False
    )
    assert (
        qualifies_for_event_pool(
            make_row(risk_type=RiskType.DATA_ANOMALY, risk_level=RiskLevel.ORANGE)
        )
        is False
    )


def test_qualifies_for_rule_explanation_orange_sales_excluded() -> None:
    row = MagicMock()
    row.scope = MonitoringScope.WAREHOUSE
    row.risk_type = RiskType.SALES_ANOMALY
    row.risk_level = RiskLevel.ORANGE
    row.requires_explanation = True
    assert qualifies_for_rule_explanation(row) is False

    row.risk_level = RiskLevel.RED
    assert qualifies_for_rule_explanation(row) is True


def test_rule_explanation_batch_speed(engine: ExplanationRuleEngine) -> None:
    """批量规则匹配应在秒级完成（无 LLM、无 DB）。"""
    import time

    started = time.perf_counter()
    for i in range(3000):
        engine.explain(
            risk_type=RiskType.STOCKOUT if i % 2 == 0 else RiskType.SLOW_MOVING,
            risk_level=RiskLevel.RED if i % 3 == 0 else RiskLevel.ORANGE,
            trigger_rule="DOS_STOCKOUT" if i % 2 == 0 else "DOS_SLOW_MOVING",
            trigger_metrics={"dos": 20},
            relief_note="缓释" if i % 10 == 0 else None,
        )
    elapsed = time.perf_counter() - started
    assert elapsed < 1.0
