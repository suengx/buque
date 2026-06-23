from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from buque.services.rule_catalog import (
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    catalog_for,
)
from buque.services.rule_config import RuleConfigService


def _pct(ratio: float) -> int:
    return int((Decimal(str(ratio)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _dos_int(value: float) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def build_metric_labels(cfg: RuleConfigService) -> dict:
    dos_red_reg = cfg.get_int("DOS_RED_REG", 30)
    dos_red_sea = cfg.get_int("DOS_RED_SEA", 45)
    slow_red_reg = cfg.get_int("SLOW_DOS_RED_REG", 150)
    slow_red_sea = cfg.get_int("SLOW_DOS_RED_SEA", 180)
    stockout_orange = cfg.get_float("STOCKOUT_ORANGE_FACTOR", 1.5)
    stockout_yellow = cfg.get_float("STOCKOUT_YELLOW_FACTOR", 2.0)
    slow_orange = cfg.get_float("SLOW_ORANGE_FACTOR", 0.85)
    slow_yellow = cfg.get_float("SLOW_YELLOW_FACTOR", 0.7)
    surge = cfg.get_float("SALES_SURGE_RATIO", 1.5)
    drop = cfg.get_float("SALES_DROP_RATIO", 0.6)

    stockout_orange_days = _dos_int(Decimal(dos_red_reg) * Decimal(str(stockout_orange)))
    stockout_yellow_days = _dos_int(Decimal(dos_red_reg) * Decimal(str(stockout_yellow)))
    slow_orange_days = _dos_int(Decimal(slow_red_reg) * Decimal(str(slow_orange)))
    slow_yellow_days = _dos_int(Decimal(slow_red_reg) * Decimal(str(slow_yellow)))

    def label(rule_code: str, text: str, short: str) -> dict:
        return {"rule_code": rule_code, "label": text, "short_label": short}

    risk_levels = {
        "RED": [
            label("DOS_RED_REG", f"DOS≤{dos_red_reg}天", "断货红"),
            label("DOS_RED_SEA", f"季节≤{dos_red_sea}天", "季节断货红"),
            label("SLOW_DOS_RED_REG", f"滞销≥{slow_red_reg}天", "滞销红"),
            label("SLOW_DOS_RED_SEA", f"季节滞销≥{slow_red_sea}天", "季节滞销红"),
        ],
        "ORANGE": [
            label("DOS_RED_REG", f"DOS≤{stockout_orange_days}天", "断货橙"),
            label("SLOW_DOS_RED_REG", f"滞销≥{slow_orange_days}天", "滞销橙"),
            label("SALES_DROP_RATIO", f"销量≤{_pct(drop)}%", "销量突降"),
        ],
        "YELLOW": [
            label("DOS_RED_REG", f"DOS≤{stockout_yellow_days}天", "断货黄"),
            label("SLOW_DOS_RED_REG", f"滞销≥{slow_yellow_days}天", "滞销黄"),
            label("SALES_SURGE_RATIO", f"销量≥{_pct(surge)}%", "销量突增"),
        ],
        "GREEN": [
            label("", "未触发上述阈值", "正常"),
        ],
    }

    if cfg.get_bool("KEY_SKU_UPGRADE"):
        risk_levels["RED"].append(label("KEY_SKU_UPGRADE", "重点链接升档", "升档"))

    special_risks = {
        "STOCKOUT": [
            label("DOS_RED_REG", f"DOS≤{dos_red_reg}天", "断货红"),
            label("STOCKOUT_ORANGE_FACTOR", f"DOS≤{stockout_orange_days}天", "断货橙"),
        ],
        "SLOW_MOVING": [
            label("SLOW_DOS_RED_REG", f"滞销≥{slow_red_reg}天", "滞销红"),
            label("SLOW_ORANGE_FACTOR", f"滞销≥{slow_orange_days}天", "滞销橙"),
        ],
    }

    if cfg.get_bool("INBOUND_RELIEF_DOWNGRADE"):
        special_risks["STOCKOUT"].append(
            label("INBOUND_RELIEF_DOWNGRADE", "在途缓释降档", "缓释")
        )

    return {
        "risk_levels": risk_levels,
        "special_risks": special_risks,
        "section_descriptions": {
            "risk_levels": "按可售天数 DOS 与近3天/近15天销量比值划档（常规品基准）",
            "special_risks": "断货/滞销类型中处于红橙档的 SKU（指标口径同上）",
        },
    }


def build_rules_grouped(cfg: RuleConfigService, rules: list) -> list[dict]:
    by_category: dict[str, list] = {c: [] for c in CATEGORY_ORDER}
    for row in rules:
        meta = catalog_for(row.rule_code)
        by_category.setdefault(meta.category, []).append(
            {
                "rule_code": row.rule_code,
                "rule_name": row.rule_name,
                "param_value": row.param_value,
                "param_type": row.param_type,
                "version": row.version,
                "effective_date": row.effective_date,
                "is_enabled": row.is_enabled,
                "change_reason": row.change_reason,
                "proposer": row.proposer,
                "category": meta.category,
                "category_label": CATEGORY_LABELS.get(meta.category, meta.category),
                "description": meta.description,
                "editor": meta.editor,
            }
        )
    groups = []
    for cat in CATEGORY_ORDER:
        items = by_category.get(cat, [])
        if not items:
            continue
        groups.append(
            {
                "category": cat,
                "category_label": CATEGORY_LABELS.get(cat, cat),
                "rules": sorted(items, key=lambda x: x["rule_code"]),
            }
        )
    return groups
