"""DOS 判级可视化结构，写入 trigger_metrics.judgment。"""

from __future__ import annotations

from decimal import Decimal

from buque.models.entities import RiskLevel

LEVEL_LABEL = {
    "RED": "红灯",
    "ORANGE": "橙灯",
    "YELLOW": "黄灯",
    "GREEN": "绿灯",
}


def _stockout_base_level(
    dos: Decimal, threshold_red: int, orange_factor: Decimal, yellow_factor: Decimal
) -> RiskLevel:
    if dos <= threshold_red:
        return RiskLevel.RED
    if dos <= Decimal(threshold_red) * orange_factor:
        return RiskLevel.ORANGE
    if dos <= Decimal(threshold_red) * yellow_factor:
        return RiskLevel.YELLOW
    return RiskLevel.GREEN


def _slow_base_level(
    dos: Decimal, threshold_red: int, orange_factor: Decimal, yellow_factor: Decimal
) -> RiskLevel:
    if dos >= threshold_red:
        return RiskLevel.RED
    if dos >= Decimal(threshold_red) * orange_factor:
        return RiskLevel.ORANGE
    if dos >= Decimal(threshold_red) * yellow_factor:
        return RiskLevel.YELLOW
    return RiskLevel.GREEN


def _stockout_bands(threshold_red: int, orange_days: float, yellow_days: float) -> list[dict]:
    return [
        {"level": "RED", "label": f"DOS ≤ {threshold_red} 天"},
        {"level": "ORANGE", "label": f"{threshold_red} < DOS ≤ {orange_days:.0f} 天"},
        {"level": "YELLOW", "label": f"{orange_days:.0f} < DOS ≤ {yellow_days:.0f} 天"},
        {"level": "GREEN", "label": f"DOS > {yellow_days:.0f} 天"},
    ]


def _slow_bands(threshold_red: int, orange_days: float, yellow_days: float) -> list[dict]:
    return [
        {"level": "RED", "label": f"DOS ≥ {threshold_red} 天"},
        {"level": "ORANGE", "label": f"{orange_days:.0f} ≤ DOS < {threshold_red} 天"},
        {"level": "YELLOW", "label": f"{yellow_days:.0f} ≤ DOS < {orange_days:.0f} 天"},
        {"level": "GREEN", "label": f"DOS < {yellow_days:.0f} 天"},
    ]


def build_stockout_judgment(
    *,
    dos: Decimal,
    threshold_red: int,
    orange_factor: Decimal,
    yellow_factor: Decimal,
    base_level: RiskLevel,
    final_level: RiskLevel,
    modifiers: list[dict],
) -> dict:
    orange_days = float(Decimal(threshold_red) * orange_factor)
    yellow_days = float(Decimal(threshold_red) * yellow_factor)
    return {
        "kind": "stockout_dos",
        "formula": "可售库存 ÷ 有效参考日销",
        "compare": "low_is_worse",
        "dos": float(dos),
        "threshold_red": threshold_red,
        "threshold_orange": orange_days,
        "threshold_yellow": yellow_days,
        "base_level": base_level.value,
        "base_level_label": LEVEL_LABEL[base_level.value],
        "final_level": final_level.value,
        "final_level_label": LEVEL_LABEL[final_level.value],
        "modifiers": modifiers,
        "bands": _stockout_bands(threshold_red, orange_days, yellow_days),
    }


def build_slow_judgment(
    *,
    dos: Decimal,
    threshold_red: int,
    orange_factor: Decimal,
    yellow_factor: Decimal,
    base_level: RiskLevel,
    final_level: RiskLevel,
    modifiers: list[dict],
) -> dict:
    orange_days = float(Decimal(threshold_red) * orange_factor)
    yellow_days = float(Decimal(threshold_red) * yellow_factor)
    return {
        "kind": "slow_moving_dos",
        "formula": "可售库存 ÷ 有效参考日销",
        "compare": "high_is_worse",
        "dos": float(dos),
        "threshold_red": threshold_red,
        "threshold_orange": orange_days,
        "threshold_yellow": yellow_days,
        "base_level": base_level.value,
        "base_level_label": LEVEL_LABEL[base_level.value],
        "final_level": final_level.value,
        "final_level_label": LEVEL_LABEL[final_level.value],
        "modifiers": modifiers,
        "bands": _slow_bands(threshold_red, orange_days, yellow_days),
    }


def build_sales_judgment(
    *,
    rule: str,
    s3: float,
    s15: float,
    ratio: float,
    drop_ratio: float,
    surge_ratio: float,
    final_level: RiskLevel,
) -> dict:
    if rule == "SALES_DROP":
        threshold = drop_ratio
        compare_label = f"近 3 天 ÷ 近 15 天 ≤ {threshold:.0%}"
    else:
        threshold = surge_ratio
        compare_label = f"近 3 天 ÷ 近 15 天 ≥ {threshold:.0%}"
    return {
        "kind": "sales_ratio",
        "formula": "近 3 天日均 ÷ 近 15 天日均",
        "compare": "ratio",
        "sales_3d_avg": s3,
        "sales_15d_avg": s15,
        "ratio": ratio,
        "threshold": threshold,
        "compare_label": compare_label,
        "base_level": final_level.value,
        "base_level_label": LEVEL_LABEL[final_level.value],
        "final_level": final_level.value,
        "final_level_label": LEVEL_LABEL[final_level.value],
        "modifiers": [],
        "bands": [],
    }
