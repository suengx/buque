from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from buque.models.entities import (
    DimSku,
    FactInboundBatch,
    FactInventoryDaily,
    FactSalesDaily,
    MonitoringScope,
    RiskLevel,
    RiskType,
)
from buque.services.dos_judgment import (
    _slow_base_level,
    _stockout_base_level,
    build_sales_judgment,
    build_slow_judgment,
    build_stockout_judgment,
)
from buque.services.ref_daily_sales import SUPPORTED_SALES_PRIORITY, resolve_ref_daily_sales
from buque.services.rule_config import RuleConfigService

ZERO = Decimal("0")
LEVEL_ORDER = [RiskLevel.GREEN, RiskLevel.YELLOW, RiskLevel.ORANGE, RiskLevel.RED]


def _dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if dec.is_nan():
        return None
    return dec


def _valid_sales(value: Any) -> bool:
    dec = _dec(value)
    if dec is None:
        return False
    try:
        return dec > 0
    except InvalidOperation:
        return False


def _upgrade(level: RiskLevel, steps: int = 1) -> RiskLevel:
    idx = min(LEVEL_ORDER.index(level) + steps, len(LEVEL_ORDER) - 1)
    return LEVEL_ORDER[idx]


def _dos_threshold(seasonality: str | None, reg_code: str, sea_code: str, cfg: RuleConfigService) -> int:
    if seasonality and "季节" in seasonality:
        return cfg.get_int(sea_code, 45)
    return cfg.get_int(reg_code, 30)


@dataclass
class MonitorFinding:
    sku: str
    warehouse: str | None
    channel: str | None
    scope: MonitoringScope
    risk_type: RiskType
    risk_level: RiskLevel
    trigger_rule: str
    trigger_metrics: dict
    dos: Decimal | None
    ref_daily_sales: Decimal | None
    available_inventory: int | None
    inbound_relief_applied: bool = False
    relief_note: str | None = None
    requires_explanation: bool = False
    requires_human_confirm: bool = False


def _dos_trigger_metrics(
    *,
    dos: Decimal,
    threshold_red: int,
    threshold_orange: float,
    threshold_yellow: float,
    available: int,
    erp_ref: Decimal | None,
    effective_ref: Decimal,
    ref_source: str,
    trim_applied: bool,
    sales_metrics: dict,
    judgment: dict,
) -> dict:
    s3 = sales_metrics.get("sales_3d_avg", ZERO)
    s15 = sales_metrics.get("sales_15d_avg", ZERO)
    return {
        "judgment": judgment,
        "available_inventory": available,
        "erp_ref_daily_sales": float(erp_ref) if erp_ref is not None else None,
        "ref_daily_sales": float(effective_ref),
        "ref_sales_source": ref_source,
        "sales_spike_trim_applied": trim_applied,
        "dos": float(dos),
        "threshold_red": threshold_red,
        "threshold_orange": threshold_orange,
        "threshold_yellow": threshold_yellow,
        "sales_3d_avg": float(s3),
        "sales_15d_avg": float(s15),
    }


class RuleEngine:
    def __init__(
        self,
        db: Session,
        monitor_date: date,
        snapshot_id: int,
        cfg: RuleConfigService | None = None,
    ):
        self.db = db
        self.monitor_date = monitor_date
        self.snapshot_id = snapshot_id
        self.cfg = cfg or RuleConfigService(db)

    def run(self) -> list[MonitorFinding]:
        findings: list[MonitorFinding] = []
        findings.extend(self._evaluate_warehouse_scope())
        findings.extend(self._evaluate_global_scope())
        findings.extend(self._evaluate_channel_scope())
        return findings

    def _evaluate_warehouse_scope(self) -> list[MonitorFinding]:
        rows = (
            self.db.query(FactInventoryDaily, DimSku)
            .join(DimSku, DimSku.sku == FactInventoryDaily.sku)
            .filter(FactInventoryDaily.snapshot_id == self.snapshot_id)
            .all()
        )
        findings: list[MonitorFinding] = []
        for inv, sku in rows:
            sales_metrics = self._sales_metrics(
                inv.sku, inv.warehouse, MonitoringScope.WAREHOUSE
            )
            priority = self.cfg.get_str("BASE_SALES_PRIORITY", "ERP_7D_AVG").strip()
            if priority not in SUPPORTED_SALES_PRIORITY:
                findings.append(
                    MonitorFinding(
                        sku=inv.sku,
                        warehouse=inv.warehouse,
                        channel=None,
                        scope=MonitoringScope.WAREHOUSE,
                        risk_type=RiskType.DATA_ANOMALY,
                        risk_level=RiskLevel.GREEN,
                        trigger_rule="MISSING_DATA_BLOCK",
                        trigger_metrics={
                            "field": "BASE_SALES_PRIORITY",
                            "ref_sales_source": priority,
                        },
                        dos=None,
                        ref_daily_sales=_dec(inv.ref_daily_sales),
                        available_inventory=inv.available_inventory,
                        requires_explanation=False,
                    )
                )
                continue

            erp_ref = _dec(inv.ref_daily_sales)
            ref, source, trimmed = resolve_ref_daily_sales(
                erp_ref, sales_metrics, self.cfg
            )
            if not _valid_sales(ref):
                findings.append(
                    MonitorFinding(
                        sku=inv.sku,
                        warehouse=inv.warehouse,
                        channel=None,
                        scope=MonitoringScope.WAREHOUSE,
                        risk_type=RiskType.DATA_ANOMALY,
                        risk_level=RiskLevel.GREEN,
                        trigger_rule="MISSING_DATA_BLOCK",
                        trigger_metrics={"field": "ref_daily_sales"},
                        dos=None,
                        ref_daily_sales=erp_ref,
                        available_inventory=inv.available_inventory,
                        requires_explanation=False,
                    )
                )
                continue

            dos = Decimal(inv.available_inventory) / ref
            findings.extend(
                self._stockout_and_slow(
                    sku=inv.sku,
                    warehouse=inv.warehouse,
                    seasonality=sku.seasonality,
                    is_key=sku.is_key_listing,
                    dos=dos,
                    erp_ref=erp_ref,
                    ref_daily_sales=ref,
                    ref_source=source,
                    trim_applied=trimmed,
                    available=inv.available_inventory,
                    sales_metrics=sales_metrics,
                )
            )
            findings.extend(
                self._sales_anomaly(
                    sku=inv.sku,
                    warehouse=inv.warehouse,
                    scope=MonitoringScope.WAREHOUSE,
                    sales_metrics=sales_metrics,
                    dos=dos,
                    ref_daily_sales=ref,
                    available=inv.available_inventory,
                )
            )
        return findings

    def _evaluate_global_scope(self) -> list[MonitorFinding]:
        sku_rows = self.db.query(FactInventoryDaily).filter(
            FactInventoryDaily.snapshot_id == self.snapshot_id
        ).all()
        by_sku: dict[str, list[FactInventoryDaily]] = {}
        for row in sku_rows:
            by_sku.setdefault(row.sku, []).append(row)

        findings: list[MonitorFinding] = []
        for sku_code, rows in by_sku.items():
            sku = self.db.get(DimSku, sku_code)
            if not sku:
                continue
            total_avail = sum(r.available_inventory for r in rows)
            ref_sales = ZERO
            for r in rows:
                sm = self._sales_metrics(r.sku, r.warehouse, MonitoringScope.WAREHOUSE)
                resolved, _, _ = resolve_ref_daily_sales(_dec(r.ref_daily_sales), sm, self.cfg)
                if _valid_sales(resolved):
                    ref_sales += resolved
            if not _valid_sales(ref_sales):
                continue
            dos = Decimal(total_avail) / ref_sales
            sales_metrics = self._sales_metrics(sku_code, None, MonitoringScope.GLOBAL)
            findings.extend(
                self._stockout_and_slow(
                    sku=sku_code,
                    warehouse=None,
                    seasonality=sku.seasonality,
                    is_key=sku.is_key_listing,
                    dos=dos,
                    erp_ref=None,
                    ref_daily_sales=ref_sales,
                    ref_source=self.cfg.get_str("BASE_SALES_PRIORITY", "ERP_7D_AVG"),
                    trim_applied=False,
                    available=total_avail,
                    sales_metrics=sales_metrics,
                    scope=MonitoringScope.GLOBAL,
                )
            )
        return findings

    def _evaluate_channel_scope(self) -> list[MonitorFinding]:
        sales = (
            self.db.query(FactSalesDaily)
            .filter(
                FactSalesDaily.snapshot_id == self.snapshot_id,
                FactSalesDaily.date == self.monitor_date,
                FactSalesDaily.sku.isnot(None),
            )
            .all()
        )
        by_key: dict[tuple[str, str], int] = {}
        for row in sales:
            key = (row.sku, row.channel)
            by_key[key] = by_key.get(key, 0) + row.order_qty

        findings: list[MonitorFinding] = []
        for (sku_code, channel), qty in by_key.items():
            sku = self.db.get(DimSku, sku_code)
            if not sku:
                continue
            avg_daily = Decimal(qty) / Decimal("7")
            if avg_daily <= 0:
                continue
            inv_total = (
                self.db.query(FactInventoryDaily)
                .filter(
                    FactInventoryDaily.snapshot_id == self.snapshot_id,
                    FactInventoryDaily.sku == sku_code,
                )
                .all()
            )
            total_avail = sum(r.available_inventory for r in inv_total)
            dos = Decimal(total_avail) / avg_daily if avg_daily > 0 else None
            if dos is None:
                continue
            sales_metrics = self._sales_metrics(sku_code, None, MonitoringScope.CHANNEL, channel=channel)
            findings.extend(
                self._sales_anomaly(
                    sku=sku_code,
                    warehouse=None,
                    channel=channel,
                    scope=MonitoringScope.CHANNEL,
                    sales_metrics=sales_metrics,
                    dos=dos,
                    ref_daily_sales=avg_daily,
                    available=total_avail,
                )
            )
        return findings

    def _sales_metrics(
        self,
        sku: str,
        warehouse: str | None,
        scope: MonitoringScope,
        channel: str | None = None,
    ) -> dict[str, Decimal]:
        q = self.db.query(FactSalesDaily).filter(
            FactSalesDaily.snapshot_id == self.snapshot_id,
            FactSalesDaily.date <= self.monitor_date,
            FactSalesDaily.sku == sku,
        )
        if scope == MonitoringScope.WAREHOUSE and warehouse:
            q = q.filter(FactSalesDaily.warehouse == warehouse)
        elif scope == MonitoringScope.CHANNEL and channel:
            q = q.filter(FactSalesDaily.channel == channel)
        rows = q.order_by(FactSalesDaily.date.desc()).limit(30).all()
        if not rows:
            return {"sales_3d_avg": ZERO, "sales_15d_avg": ZERO}

        by_date: dict[date, int] = {}
        for r in rows:
            by_date[r.date] = by_date.get(r.date, 0) + r.order_qty
        sorted_dates = sorted(by_date.keys(), reverse=True)
        s3 = sum(by_date[d] for d in sorted_dates[:3])
        s15 = sum(by_date[d] for d in sorted_dates[:15])
        return {
            "sales_3d_avg": Decimal(s3) / Decimal(min(3, len(sorted_dates[:3]) or 1)),
            "sales_15d_avg": Decimal(s15) / Decimal(min(15, len(sorted_dates[:15]) or 1)),
        }

    def _stockout_and_slow(
        self,
        sku: str,
        warehouse: str | None,
        seasonality: str | None,
        is_key: bool,
        dos: Decimal,
        erp_ref: Decimal | None,
        ref_daily_sales: Decimal,
        ref_source: str,
        trim_applied: bool,
        available: int,
        sales_metrics: dict,
        scope: MonitoringScope = MonitoringScope.WAREHOUSE,
    ) -> list[MonitorFinding]:
        findings: list[MonitorFinding] = []
        stockout_red = _dos_threshold(seasonality, "DOS_RED_REG", "DOS_RED_SEA", self.cfg)
        slow_red = _dos_threshold(seasonality, "SLOW_DOS_RED_REG", "SLOW_DOS_RED_SEA", self.cfg)
        surge_ratio = self.cfg.get_float("SALES_SURGE_RATIO", 1.5)
        stockout_orange_factor = Decimal(str(self.cfg.get_float("STOCKOUT_ORANGE_FACTOR", 1.5)))
        stockout_yellow_factor = Decimal(str(self.cfg.get_float("STOCKOUT_YELLOW_FACTOR", 2.0)))
        slow_orange_factor = Decimal(str(self.cfg.get_float("SLOW_ORANGE_FACTOR", 0.85)))
        slow_yellow_factor = Decimal(str(self.cfg.get_float("SLOW_YELLOW_FACTOR", 0.7)))

        # 断货
        stockout_base = _stockout_base_level(
            dos, stockout_red, stockout_orange_factor, stockout_yellow_factor
        )
        stockout_level = stockout_base
        stockout_modifiers: list[dict] = []

        s3 = sales_metrics.get("sales_3d_avg", ZERO)
        s15 = sales_metrics.get("sales_15d_avg", ZERO)
        if s15 > 0 and s3 >= s15 * Decimal(str(surge_ratio)):
            prev = stockout_level
            stockout_level = _upgrade(stockout_level, 1)
            stockout_modifiers.append(
                {
                    "rule": "SALES_SURGE_RATIO",
                    "label": "销量突增升一档",
                    "from_level": prev.value,
                    "to_level": stockout_level.value,
                }
            )

        relief_applied = False
        relief_note = None
        if (
            stockout_level == RiskLevel.RED
            and self.cfg.get_bool("INBOUND_RELIEF_DOWNGRADE")
            and scope == MonitoringScope.WAREHOUSE
            and warehouse
        ):
            if self._inbound_can_relief(sku, warehouse, dos, ref_daily_sales, available):
                prev = stockout_level
                stockout_level = RiskLevel.ORANGE
                relief_applied = True
                relief_note = "需关注到货兑现"
                stockout_modifiers.append(
                    {
                        "rule": "INBOUND_RELIEF_DOWNGRADE",
                        "label": "在途缓释降一档",
                        "from_level": prev.value,
                        "to_level": stockout_level.value,
                    }
                )

        if self.cfg.get_bool("KEY_SKU_UPGRADE") and is_key and stockout_level != RiskLevel.GREEN:
            prev = stockout_level
            stockout_level = _upgrade(stockout_level, 1)
            stockout_modifiers.append(
                {
                    "rule": "KEY_SKU_UPGRADE",
                    "label": "重点链接升一档",
                    "from_level": prev.value,
                    "to_level": stockout_level.value,
                }
            )

        stockout_orange_days = float(Decimal(stockout_red) * stockout_orange_factor)
        stockout_yellow_days = float(Decimal(stockout_red) * stockout_yellow_factor)

        if stockout_level != RiskLevel.GREEN:
            findings.append(
                MonitorFinding(
                    sku=sku,
                    warehouse=warehouse,
                    channel=None,
                    scope=scope,
                    risk_type=RiskType.STOCKOUT,
                    risk_level=stockout_level,
                    trigger_rule="DOS_STOCKOUT",
                    trigger_metrics=_dos_trigger_metrics(
                        dos=dos,
                        threshold_red=stockout_red,
                        threshold_orange=stockout_orange_days,
                        threshold_yellow=stockout_yellow_days,
                        available=available,
                        erp_ref=erp_ref,
                        effective_ref=ref_daily_sales,
                        ref_source=ref_source,
                        trim_applied=trim_applied,
                        sales_metrics=sales_metrics,
                        judgment=build_stockout_judgment(
                            dos=dos,
                            threshold_red=stockout_red,
                            orange_factor=stockout_orange_factor,
                            yellow_factor=stockout_yellow_factor,
                            base_level=stockout_base,
                            final_level=stockout_level,
                            modifiers=stockout_modifiers,
                        ),
                    ),
                    dos=dos,
                    ref_daily_sales=ref_daily_sales,
                    available_inventory=available,
                    inbound_relief_applied=relief_applied,
                    relief_note=relief_note,
                    requires_explanation=stockout_level in {RiskLevel.RED, RiskLevel.ORANGE},
                    requires_human_confirm=stockout_level == RiskLevel.RED,
                )
            )

        # 滞销
        slow_base = _slow_base_level(dos, slow_red, slow_orange_factor, slow_yellow_factor)
        slow_level = slow_base
        slow_orange_days = float(Decimal(slow_red) * slow_orange_factor)
        slow_yellow_days = float(Decimal(slow_red) * slow_yellow_factor)

        if slow_level != RiskLevel.GREEN:
            findings.append(
                MonitorFinding(
                    sku=sku,
                    warehouse=warehouse,
                    channel=None,
                    scope=scope,
                    risk_type=RiskType.SLOW_MOVING,
                    risk_level=slow_level,
                    trigger_rule="DOS_SLOW_MOVING",
                    trigger_metrics=_dos_trigger_metrics(
                        dos=dos,
                        threshold_red=slow_red,
                        threshold_orange=slow_orange_days,
                        threshold_yellow=slow_yellow_days,
                        available=available,
                        erp_ref=erp_ref,
                        effective_ref=ref_daily_sales,
                        ref_source=ref_source,
                        trim_applied=trim_applied,
                        sales_metrics=sales_metrics,
                        judgment=build_slow_judgment(
                            dos=dos,
                            threshold_red=slow_red,
                            orange_factor=slow_orange_factor,
                            yellow_factor=slow_yellow_factor,
                            base_level=slow_base,
                            final_level=slow_level,
                            modifiers=[],
                        ),
                    ),
                    dos=dos,
                    ref_daily_sales=ref_daily_sales,
                    available_inventory=available,
                    requires_explanation=slow_level in {RiskLevel.RED, RiskLevel.ORANGE},
                    requires_human_confirm=slow_level == RiskLevel.RED,
                )
            )
        return findings

    def _sales_anomaly(
        self,
        sku: str,
        warehouse: str | None,
        scope: MonitoringScope,
        sales_metrics: dict,
        dos: Decimal,
        ref_daily_sales: Decimal,
        available: int,
        channel: str | None = None,
    ) -> list[MonitorFinding]:
        drop_ratio = self.cfg.get_float("SALES_DROP_RATIO", 0.6)
        surge_ratio = self.cfg.get_float("SALES_SURGE_RATIO", 1.5)
        s3 = sales_metrics.get("sales_3d_avg", ZERO)
        s15 = sales_metrics.get("sales_15d_avg", ZERO)
        if s15 <= 0:
            return []

        level = RiskLevel.GREEN
        rule = "SALES_ANOMALY"
        if s3 <= s15 * Decimal(str(drop_ratio)):
            level = RiskLevel.ORANGE
            rule = "SALES_DROP"
        elif s3 >= s15 * Decimal(str(surge_ratio)):
            level = RiskLevel.YELLOW
            rule = "SALES_SURGE"

        if level == RiskLevel.GREEN:
            return []

        ratio = float(s3 / s15) if s15 else None
        judgment = build_sales_judgment(
            rule=rule,
            s3=float(s3),
            s15=float(s15),
            ratio=ratio or 0.0,
            drop_ratio=drop_ratio,
            surge_ratio=surge_ratio,
            final_level=level,
        )

        return [
            MonitorFinding(
                sku=sku,
                warehouse=warehouse,
                channel=channel,
                scope=scope,
                risk_type=RiskType.SALES_ANOMALY,
                risk_level=level,
                trigger_rule=rule,
                trigger_metrics={
                    "judgment": judgment,
                    "sales_3d_avg": float(s3),
                    "sales_15d_avg": float(s15),
                    "ratio": ratio,
                    "dos": float(dos),
                    "available_inventory": available,
                    "ref_daily_sales": float(ref_daily_sales),
                },
                dos=dos,
                ref_daily_sales=ref_daily_sales,
                available_inventory=available,
                requires_explanation=True,
            )
        ]

    def _inbound_can_relief(
        self,
        sku: str,
        warehouse: str,
        dos: Decimal,
        ref_daily_sales: Decimal,
        available: int,
    ) -> bool:
        batches = (
            self.db.query(FactInboundBatch)
            .filter(
                FactInboundBatch.snapshot_id == self.snapshot_id,
                FactInboundBatch.sku == sku,
                FactInboundBatch.warehouse == warehouse,
                FactInboundBatch.eligible_for_relief.is_(True),
            )
            .all()
        )
        if not batches:
            return False
        total_inbound = sum(b.unreceived_qty for b in batches)
        days_to_stockout = dos
        needed = int(ref_daily_sales * days_to_stockout) - available
        return total_inbound >= max(needed, 0)
