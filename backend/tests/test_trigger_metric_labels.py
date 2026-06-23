from buque.models.entities import RiskLevel, RiskType
from buque.services.explanation_engine import ExplanationRuleEngine
from buque.services.trigger_metric_labels import build_key_evidence, format_metric_value


def test_build_key_evidence_formats_metrics() -> None:
    lines = build_key_evidence(
        "DOS_STOCKOUT",
        {"dos": 0, "threshold_red": 30, "sales_3d_avg": 0, "sales_15d_avg": 0},
    )
    assert lines[0] == "触发规则 · 断货 DOS 判级"
    assert "可售天数 DOS · 0.0 天" in lines
    assert "红灯阈值 · 30 天" in lines
    assert "近 3 天日均销量 · 0.00 件/天" in lines


def test_explanation_engine_no_raw_dict_in_evidence() -> None:
    engine = ExplanationRuleEngine()
    payload = engine.explain(
        risk_type=RiskType.STOCKOUT,
        risk_level=RiskLevel.RED,
        trigger_rule="DOS_STOCKOUT",
        trigger_metrics={"dos": 0, "threshold_red": 30},
    )
    assert all(not line.strip().startswith("{") for line in payload.key_evidence)
    assert any("可售天数 DOS" in line for line in payload.key_evidence)


def test_format_metric_value_ratio() -> None:
    assert format_metric_value("ratio", 0.6) == "60%"
