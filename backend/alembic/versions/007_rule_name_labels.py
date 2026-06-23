"""Rename rule_config.rule_name to semantic judgment-rule labels."""

from typing import Sequence, Union

from alembic import op

revision: str = "007_rule_name_labels"
down_revision: Union[str, None] = "006_rule_grade_factors"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RENAME_MAP = {
    "BASE_SALES_PRIORITY": "参考销量来源判断规则",
    "SALES_SPIKE_TRIM": "异常销量修正判断规则",
    "FORECAST_BIAS_ENABLED": "预测偏差启停判断规则",
    "INBOUND_RELIEF_DOWNGRADE": "在途缓释降档判断规则",
    "INBOUND_TMS_ELIGIBLE": "在途 TMS 状态判断规则",
    "INBOUND_NO_ETA_SCOPE": "无 ETA 在途范围判断规则",
    "DOS_RED_REG": "常规品断货红灯判断规则",
    "DOS_RED_SEA": "季节品断货红灯判断规则",
    "STOCKOUT_ORANGE_FACTOR": "断货橙灯倍率判断规则",
    "STOCKOUT_YELLOW_FACTOR": "断货黄灯倍率判断规则",
    "SALES_SURGE_RATIO": "销量突增判断规则",
    "KEY_SKU_UPGRADE": "重点链接升档判断规则",
    "SLOW_DOS_RED_REG": "常规品滞销红灯判断规则",
    "SLOW_DOS_RED_SEA": "季节品滞销红灯判断规则",
    "SLOW_ORANGE_FACTOR": "滞销橙灯倍率判断规则",
    "SLOW_YELLOW_FACTOR": "滞销黄灯倍率判断规则",
    "SALES_DROP_RATIO": "销量突降判断规则",
    "FC_ERR_RED": "预测偏差红灯判断规则",
    "MISSING_DATA_BLOCK": "关键字段缺失拦截判断规则",
    "RED_PUSH_IMMEDIATELY": "红灯即时推送判断规则",
    "CAUSE_TOP_N": "异常原因条数判断规则",
    "FEEDBACK_SAVE": "人工反馈留痕判断规则",
    "TIMEZONE": "业务时区判断规则",
}


def upgrade() -> None:
    for code, name in RENAME_MAP.items():
        safe_name = name.replace("'", "''")
        op.execute(
            f"UPDATE rule_config SET rule_name = '{safe_name}' WHERE rule_code = '{code}'"
        )


def downgrade() -> None:
    pass
