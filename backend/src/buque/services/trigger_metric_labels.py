"""触发指标字段中文标签与格式化。"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

TRIGGER_RULE_LABELS: dict[str, str] = {
    "DOS_STOCKOUT": "断货 DOS 判级",
    "DOS_SLOW_MOVING": "滞销 DOS 判级",
    "SALES_SURGE": "销量突增判级",
    "SALES_DROP": "销量突降判级",
    "SALES_ANOMALY": "销量异常判级",
    "MISSING_DATA_BLOCK": "关键字段缺失拦截",
}

METRIC_FIELDS: dict[str, tuple[str, str]] = {
    "dos": ("可售天数 DOS", "可售库存 ÷ 参考日销"),
    "threshold_red": ("红灯阈值", "规则配置的红灯 DOS 线"),
    "sales_3d_avg": ("近 3 天日均销量", "近 3 天订购量均值"),
    "sales_15d_avg": ("近 15 天日均销量", "近 15 天订购量均值"),
    "ratio": ("销量比值", "近 3 天 ÷ 近 15 天"),
    "field": ("异常字段", "数据质量拦截字段"),
}


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def format_metric_value(key: str, value: Any) -> str:
    n = _num(value)
    if n is None:
        return str(value) if value is not None else "—"
    if key == "dos":
        return f"{n:.1f} 天"
    if key == "threshold_red":
        return f"{int(n)} 天"
    if key in {"sales_3d_avg", "sales_15d_avg"}:
        return f"{n:.2f} 件/天"
    if key == "ratio":
        return f"{n * 100:.0f}%"
    return str(value)


def format_trigger_rule(rule_code: str) -> str:
    return TRIGGER_RULE_LABELS.get(rule_code, rule_code)


def build_key_evidence(trigger_rule: str, metrics: dict | None) -> list[str]:
    lines = [f"触发规则 · {format_trigger_rule(trigger_rule)}"]
    for key, value in (metrics or {}).items():
        label, _hint = METRIC_FIELDS.get(key, (key, ""))
        lines.append(f"{label} · {format_metric_value(key, value)}")
    return lines


def metrics_as_rows(metrics: dict | None) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key, value in (metrics or {}).items():
        label, hint = METRIC_FIELDS.get(key, (key, ""))
        rows.append(
            {
                "key": key,
                "label": label,
                "hint": hint,
                "value": format_metric_value(key, value),
            }
        )
    return rows
