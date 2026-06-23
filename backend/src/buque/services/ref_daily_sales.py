"""参考日销解析：按 rule_config 决定 DOS 分母，一期仅 ERP_7D_AVG。"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from buque.services.rule_config import RuleConfigService

SUPPORTED_SALES_PRIORITY = frozenset({"ERP_7D_AVG"})
ZERO = Decimal("0")


def _dec(value) -> Decimal | None:
    if value is None:
        return None
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if dec.is_nan():
        return None
    return dec


def _valid_sales(value) -> bool:
    dec = _dec(value)
    return dec is not None and dec > 0


def resolve_ref_daily_sales(
    erp_ref: Decimal | None,
    sales_metrics: dict[str, Decimal],
    cfg: RuleConfigService,
) -> tuple[Decimal | None, str, bool]:
    """返回 (有效参考日销, 来源标识, 是否应用了突增修正)。"""
    priority = cfg.get_str("BASE_SALES_PRIORITY", "ERP_7D_AVG").strip()
    if priority not in SUPPORTED_SALES_PRIORITY:
        return None, priority, False

    ref = _dec(erp_ref)
    if not _valid_sales(ref):
        return None, priority, False

    trim_applied = False
    if cfg.get_bool("SALES_SPIKE_TRIM"):
        s3 = sales_metrics.get("sales_3d_avg", ZERO)
        s15 = sales_metrics.get("sales_15d_avg", ZERO)
        surge_ratio = Decimal(str(cfg.get_float("SALES_SURGE_RATIO", 1.5)))
        if s15 > 0 and s3 >= s15 * surge_ratio and ref > s15:
            ref = s15
            trim_applied = True

    return ref, priority, trim_applied
