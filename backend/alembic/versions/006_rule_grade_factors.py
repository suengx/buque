"""Insert grade factor rule_config rows."""

from typing import Sequence, Union

from alembic import op

revision: str = "006_rule_grade_factors"
down_revision: Union[str, None] = "005_snapshot_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_RULES = (
    ("STOCKOUT_ORANGE_FACTOR", "断货橙灯倍率", "1.5", "float"),
    ("STOCKOUT_YELLOW_FACTOR", "断货黄灯倍率", "2.0", "float"),
    ("SLOW_ORANGE_FACTOR", "滞销橙灯倍率", "0.85", "float"),
    ("SLOW_YELLOW_FACTOR", "滞销黄灯倍率", "0.7", "float"),
)


def upgrade() -> None:
    for rule_code, rule_name, param_value, param_type in NEW_RULES:
        op.execute(
            f"""
            INSERT INTO rule_config (
                rule_code, rule_name, param_value, param_type,
                is_enabled, version, effective_date,
                proposer, approver, change_reason
            )
            SELECT
                '{rule_code}', '{rule_name}', '{param_value}', '{param_type}',
                true, 1, CURRENT_DATE,
                'system', 'migration', '006 橙黄档倍率配置化'
            WHERE NOT EXISTS (
                SELECT 1 FROM rule_config
                WHERE rule_code = '{rule_code}' AND version = 1
            )
            """
        )


def downgrade() -> None:
    codes = ", ".join(f"'{code}'" for code, _, _, _ in NEW_RULES)
    op.execute(f"DELETE FROM rule_config WHERE rule_code IN ({codes})")
