"""规则配置 UI 元数据（与 rule_config_seed 对齐）。"""

from __future__ import annotations

from dataclasses import dataclass

CATEGORY_ORDER = (
    "stockout",
    "slow_moving",
    "sales",
    "inbound",
    "upgrade",
    "forecast",
    "quality",
    "ai",
    "system",
)

CATEGORY_LABELS: dict[str, str] = {
    "stockout": "断货风险",
    "slow_moving": "滞销风险",
    "sales": "销量异常",
    "inbound": "在途缓释",
    "upgrade": "升级规则",
    "forecast": "预测偏差",
    "quality": "数据质量",
    "ai": "AI 解释",
    "system": "系统",
}


@dataclass(frozen=True)
class RuleCatalogEntry:
    rule_code: str
    category: str
    description: str
    editor: str  # int | float | bool | string | tags


RULE_CATALOG: dict[str, RuleCatalogEntry] = {
    "BASE_SALES_PRIORITY": RuleCatalogEntry(
        "BASE_SALES_PRIORITY",
        "system",
        "一期固定取 ERP 7 天日均作为参考销量",
        "string",
    ),
    "SALES_SPIKE_TRIM": RuleCatalogEntry(
        "SALES_SPIKE_TRIM",
        "system",
        "缺货日剔除、活动冲高标记等销量修正；一期默认关闭",
        "bool",
    ),
    "FORECAST_BIAS_ENABLED": RuleCatalogEntry(
        "FORECAST_BIAS_ENABLED",
        "forecast",
        "预测偏差规则总开关；一期关闭",
        "bool",
    ),
    "INBOUND_RELIEF_DOWNGRADE": RuleCatalogEntry(
        "INBOUND_RELIEF_DOWNGRADE",
        "inbound",
        "断货红灯且 ETA 窗口内在途可覆盖缺口时，降一级为橙灯",
        "bool",
    ),
    "INBOUND_TMS_ELIGIBLE": RuleCatalogEntry(
        "INBOUND_TMS_ELIGIBLE",
        "inbound",
        "可参与在途缓释的 TMS 状态，逗号分隔",
        "tags",
    ),
    "INBOUND_NO_ETA_SCOPE": RuleCatalogEntry(
        "INBOUND_NO_ETA_SCOPE",
        "inbound",
        "无 ETA 仓内在途处理范围",
        "string",
    ),
    "DOS_RED_REG": RuleCatalogEntry(
        "DOS_RED_REG",
        "stockout",
        "常规品可售天数 DOS 低于等于该值进入断货红灯",
        "int",
    ),
    "DOS_RED_SEA": RuleCatalogEntry(
        "DOS_RED_SEA",
        "stockout",
        "季节品断货红灯 DOS 阈值（通常高于常规品）",
        "int",
    ),
    "STOCKOUT_ORANGE_FACTOR": RuleCatalogEntry(
        "STOCKOUT_ORANGE_FACTOR",
        "stockout",
        "断货橙灯：DOS ≤ 红灯阈值 × 该倍率",
        "float",
    ),
    "STOCKOUT_YELLOW_FACTOR": RuleCatalogEntry(
        "STOCKOUT_YELLOW_FACTOR",
        "stockout",
        "断货黄灯：DOS ≤ 红灯阈值 × 该倍率",
        "float",
    ),
    "SALES_SURGE_RATIO": RuleCatalogEntry(
        "SALES_SURGE_RATIO",
        "sales",
        "近 3 天日均 / 近 15 天日均 ≥ 该比值触发销量突增",
        "float",
    ),
    "KEY_SKU_UPGRADE": RuleCatalogEntry(
        "KEY_SKU_UPGRADE",
        "upgrade",
        "断货/滞销已触发时，对 dim_sku.is_key_listing=true 的 SKU 预警上调一级；参数「开启」才生效，SKU 标记由 focus_skus 或主数据维护",
        "bool",
    ),
    "SLOW_DOS_RED_REG": RuleCatalogEntry(
        "SLOW_DOS_RED_REG",
        "slow_moving",
        "常规品 DOS 高于等于该值进入滞销红灯",
        "int",
    ),
    "SLOW_DOS_RED_SEA": RuleCatalogEntry(
        "SLOW_DOS_RED_SEA",
        "slow_moving",
        "季节品滞销红灯 DOS 阈值",
        "int",
    ),
    "SLOW_ORANGE_FACTOR": RuleCatalogEntry(
        "SLOW_ORANGE_FACTOR",
        "slow_moving",
        "滞销橙灯：DOS ≥ 红灯阈值 × 该倍率",
        "float",
    ),
    "SLOW_YELLOW_FACTOR": RuleCatalogEntry(
        "SLOW_YELLOW_FACTOR",
        "slow_moving",
        "滞销黄灯：DOS ≥ 红灯阈值 × 该倍率",
        "float",
    ),
    "SALES_DROP_RATIO": RuleCatalogEntry(
        "SALES_DROP_RATIO",
        "sales",
        "近 3 天日均 / 近 15 天日均 ≤ 该比值触发销量突降（橙灯）",
        "float",
    ),
    "FC_ERR_RED": RuleCatalogEntry(
        "FC_ERR_RED",
        "forecast",
        "预测绝对偏差率超过该值进入红灯（需开启预测偏差规则）",
        "float",
    ),
    "MISSING_DATA_BLOCK": RuleCatalogEntry(
        "MISSING_DATA_BLOCK",
        "quality",
        "缺库存/销量时阻断 DOS 计算并标记数据异常",
        "bool",
    ),
    "RED_PUSH_IMMEDIATELY": RuleCatalogEntry(
        "RED_PUSH_IMMEDIATELY",
        "upgrade",
        "红灯 SKU 触发即时推送",
        "bool",
    ),
    "CAUSE_TOP_N": RuleCatalogEntry(
        "CAUSE_TOP_N",
        "ai",
        "Agent 解释输出候选原因条数",
        "int",
    ),
    "FEEDBACK_SAVE": RuleCatalogEntry(
        "FEEDBACK_SAVE",
        "ai",
        "人工反馈留痕开关",
        "bool",
    ),
    "TIMEZONE": RuleCatalogEntry(
        "TIMEZONE",
        "system",
        "业务时区，影响调度与展示",
        "string",
    ),
}


def catalog_for(rule_code: str) -> RuleCatalogEntry:
    entry = RULE_CATALOG.get(rule_code)
    if entry is None:
        return RuleCatalogEntry(rule_code, "system", "", "string")
    return entry
