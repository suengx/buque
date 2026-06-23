from decimal import Decimal

from buque.models.entities import RiskLevel
from buque.services.dos_judgment import build_stockout_judgment


def test_stockout_judgment_orange_base_with_key_upgrade_modifier() -> None:
    """DOS=31、红灯 30 → 基准橙灯；升一档修正后终态黄灯。"""
    j = build_stockout_judgment(
        dos=Decimal("31"),
        threshold_red=30,
        orange_factor=Decimal("1.5"),
        yellow_factor=Decimal("2.0"),
        base_level=RiskLevel.ORANGE,
        final_level=RiskLevel.YELLOW,
        modifiers=[
            {
                "rule": "KEY_SKU_UPGRADE",
                "label": "重点链接升一档",
                "from_level": "ORANGE",
                "to_level": "YELLOW",
            }
        ],
    )
    assert j["base_level"] == "ORANGE"
    assert j["final_level"] == "YELLOW"
    assert len(j["modifiers"]) == 1
    assert j["threshold_orange"] == 45.0
    assert any("30 < DOS ≤ 45" in b["label"] for b in j["bands"])
