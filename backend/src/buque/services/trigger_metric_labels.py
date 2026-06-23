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
    "available_inventory": ("可售库存", "DOS 分子，不含在途"),
    "erp_ref_daily_sales": ("ERP 7 天日均", "产品库存页原始参考日销"),
    "ref_daily_sales": ("有效参考日销", "经 BASE_SALES_PRIORITY / SALES_SPIKE_TRIM 后的 DOS 分母"),
    "ref_sales_source": ("参考日销来源", "BASE_SALES_PRIORITY 配置值"),
    "sales_spike_trim_applied": ("突增修正", "SALES_SPIKE_TRIM 是否压低分母"),
    "dos": ("可售天数 DOS", "可售库存 ÷ 有效参考日销"),
    "threshold_red": ("红灯阈值", "规则配置的红灯 DOS 线"),
    "sales_3d_avg": ("近 3 天日均销量", "订单 rollup，辅助突增/异常判级"),
    "sales_15d_avg": ("近 15 天日均销量", "订单 rollup，辅助突增/异常判级"),
    "ratio": ("销量比值", "近 3 天 ÷ 近 15 天"),
    "field": ("异常字段", "数据质量拦截字段"),
}

DOS_BASIS_KEYS = (
    "available_inventory",
    "erp_ref_daily_sales",
    "ref_daily_sales",
    "ref_sales_source",
    "sales_spike_trim_applied",
    "dos",
    "threshold_red",
)

SALES_AUX_KEYS = ("sales_3d_avg", "sales_15d_avg", "ratio")

REF_SALES_SOURCE_LABELS = {
    "ERP_7D_AVG": "ERP 7 天日均",
}


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def format_metric_value(key: str, value: Any) -> str:
    if key == "sales_spike_trim_applied":
        return "已应用" if value in {True, "true", "True", 1} else "未应用"
    if key == "ref_sales_source":
        return REF_SALES_SOURCE_LABELS.get(str(value), str(value)) if value is not None else "—"
    n = _num(value)
    if n is None:
        return str(value) if value is not None else "—"
    if key == "dos":
        return f"{n:.1f} 天"
    if key == "threshold_red":
        return f"{int(n)} 天"
    if key in {"sales_3d_avg", "sales_15d_avg", "erp_ref_daily_sales", "ref_daily_sales"}:
        return f"{n:.2f} 件/天"
    if key == "available_inventory":
        return f"{int(n)} 件"
    if key == "ratio":
        return f"{n * 100:.0f}%"
    return str(value)


def format_trigger_rule(rule_code: str) -> str:
    return TRIGGER_RULE_LABELS.get(rule_code, rule_code)


def build_key_evidence(trigger_rule: str, metrics: dict | None) -> list[str]:
    lines = [f"触发规则 · {format_trigger_rule(trigger_rule)}"]
    m = metrics or {}
    for key in DOS_BASIS_KEYS:
        if key not in m:
            continue
        label, _hint = METRIC_FIELDS.get(key, (key, ""))
        lines.append(f"{label} · {format_metric_value(key, m[key])}")
    for key in SALES_AUX_KEYS:
        if key not in m:
            continue
        label, _hint = METRIC_FIELDS.get(key, (key, ""))
        lines.append(f"{label} · {format_metric_value(key, m[key])}")
    if "field" in m:
        label, _ = METRIC_FIELDS["field"]
        lines.append(f"{label} · {format_metric_value('field', m['field'])}")
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
