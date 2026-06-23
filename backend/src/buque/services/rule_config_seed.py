"""一期默认 rule_config 种子（对齐 CONTEXT.md + 05_RULES_AND_OUTPUTS.md）"""

from datetime import date

RULE_CONFIG_SEED: list[dict] = [
    {
        "rule_code": "BASE_SALES_PRIORITY",
        "rule_name": "参考销量来源判断规则",
        "param_value": "ERP_7D_AVG",
        "param_type": "string",
    },
    {
        "rule_code": "SALES_SPIKE_TRIM",
        "rule_name": "异常销量修正判断规则",
        "param_value": "false",
        "param_type": "bool",
    },
    {
        "rule_code": "FORECAST_BIAS_ENABLED",
        "rule_name": "预测偏差启停判断规则",
        "param_value": "false",
        "param_type": "bool",
    },
    {
        "rule_code": "INBOUND_RELIEF_DOWNGRADE",
        "rule_name": "在途缓释降档判断规则",
        "param_value": "true",
        "param_type": "bool",
    },
    {
        "rule_code": "INBOUND_TMS_ELIGIBLE",
        "rule_name": "在途 TMS 状态判断规则",
        "param_value": "已出运,入库中",
        "param_type": "string",
    },
    {
        "rule_code": "INBOUND_NO_ETA_SCOPE",
        "rule_name": "无 ETA 在途范围判断规则",
        "param_value": "display_only",
        "param_type": "string",
    },
    {
        "rule_code": "DOS_RED_REG",
        "rule_name": "常规品断货红灯判断规则",
        "param_value": "30",
        "param_type": "int",
    },
    {
        "rule_code": "DOS_RED_SEA",
        "rule_name": "季节品断货红灯判断规则",
        "param_value": "45",
        "param_type": "int",
    },
    {
        "rule_code": "STOCKOUT_ORANGE_FACTOR",
        "rule_name": "断货橙灯倍率判断规则",
        "param_value": "1.5",
        "param_type": "float",
    },
    {
        "rule_code": "STOCKOUT_YELLOW_FACTOR",
        "rule_name": "断货黄灯倍率判断规则",
        "param_value": "2.0",
        "param_type": "float",
    },
    {
        "rule_code": "SALES_SURGE_RATIO",
        "rule_name": "销量突增判断规则",
        "param_value": "1.5",
        "param_type": "float",
    },
    {
        "rule_code": "KEY_SKU_UPGRADE",
        "rule_name": "重点链接升档判断规则",
        "param_value": "true",
        "param_type": "bool",
    },
    {
        "rule_code": "SLOW_DOS_RED_REG",
        "rule_name": "常规品滞销红灯判断规则",
        "param_value": "150",
        "param_type": "int",
    },
    {
        "rule_code": "SLOW_DOS_RED_SEA",
        "rule_name": "季节品滞销红灯判断规则",
        "param_value": "180",
        "param_type": "int",
    },
    {
        "rule_code": "SLOW_ORANGE_FACTOR",
        "rule_name": "滞销橙灯倍率判断规则",
        "param_value": "0.85",
        "param_type": "float",
    },
    {
        "rule_code": "SLOW_YELLOW_FACTOR",
        "rule_name": "滞销黄灯倍率判断规则",
        "param_value": "0.7",
        "param_type": "float",
    },
    {
        "rule_code": "SALES_DROP_RATIO",
        "rule_name": "销量突降判断规则",
        "param_value": "0.6",
        "param_type": "float",
    },
    {
        "rule_code": "FC_ERR_RED",
        "rule_name": "预测偏差红灯判断规则",
        "param_value": "0.5",
        "param_type": "float",
    },
    {
        "rule_code": "MISSING_DATA_BLOCK",
        "rule_name": "关键字段缺失拦截判断规则",
        "param_value": "true",
        "param_type": "bool",
    },
    {
        "rule_code": "RED_PUSH_IMMEDIATELY",
        "rule_name": "红灯即时推送判断规则",
        "param_value": "true",
        "param_type": "bool",
    },
    {
        "rule_code": "CAUSE_TOP_N",
        "rule_name": "异常原因条数判断规则",
        "param_value": "3",
        "param_type": "int",
    },
    {
        "rule_code": "FEEDBACK_SAVE",
        "rule_name": "人工反馈留痕判断规则",
        "param_value": "true",
        "param_type": "bool",
    },
    {
        "rule_code": "TIMEZONE",
        "rule_name": "业务时区判断规则",
        "param_value": "Asia/Shanghai",
        "param_type": "string",
    },
]

SEED_EFFECTIVE_DATE = date(2026, 6, 22)
