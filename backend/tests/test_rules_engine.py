from decimal import Decimal

from buque.rules.engine import _upgrade
from buque.models.entities import RiskLevel


def test_upgrade_level() -> None:
    assert _upgrade(RiskLevel.GREEN, 1) == RiskLevel.YELLOW
    assert _upgrade(RiskLevel.RED, 1) == RiskLevel.RED


def test_dos_calculation() -> None:
    available = 25
    ref_daily = Decimal("8")
    dos = Decimal(available) / ref_daily
    assert dos == Decimal("3.125")
