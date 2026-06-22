from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
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
from buque.services.rule_config import RuleConfigService

ZERO = Decimal("0")
LEVEL_ORDER = [RiskLevel.GREEN, RiskLevel.YELLOW, RiskLevel.ORANGE, RiskLevel.RED]


def _dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


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


class RuleEngine:
    def __init__(self, db: Session, monitor_date: date, cfg: RuleConfigService | None = None):
        self.db = db
        self.monitor_date = monitor_date
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
            .filter(FactInventoryDaily.date == self.monitor_date)
            .all()
        )
        findings: list[MonitorFinding] = []
        for inv, sku in rows:
            if inv.ref_daily_sales is None or inv.ref_daily_sales <= 0:
                findings.append(
                    MonitorFinding(
                        sku=inv.sku,
                        warehouse=inv.warehouse,
                        channel=None,
                        scope=MonitoringScope.WAREHOUSE,
                        risk_type=RiskType.DATA_ANOMALY,
                        risk_level=RiskLevel.ORANGE,
                        trigger_rule="MISSING_DATA_BLOCK",
                        trigger_metrics={"field": "ref_daily_sales"},
                        dos=None,
                        ref_daily_sales=_dec(inv.ref_daily_sales),
                        available_inventory=inv.available_inventory,
                        requires_explanation=True,
                    )
                )
                continue

            dos = Decimal(inv.available_inventory) / Decimal(inv.ref_daily_sales)
            sales_metrics = self._sales_metrics(inv.sku, inv.warehouse, MonitoringScope.WAREHOUSE)
            findings.extend(
                self._stockout_and_slow(
                    sku=inv.sku,
                    warehouse=inv.warehouse,
                    seasonality=sku.seasonality,
                    is_key=sku.is_key_listing,
                    dos=dos,
                    ref_daily_sales=_dec(inv.ref_daily_sales),
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
                    ref_daily_sales=_dec(inv.ref_daily_sales),
                    available=inv.available_inventory,
                )
            )
        return findings

    def _evaluate_global_scope(self) -> list[MonitorFinding]:
        sku_rows = self.db.query(FactInventoryDaily).filter(
            FactInventoryDaily.date == self.monitor_date
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
            ref_sales = sum(
                Decimal(r.ref_daily_sales or 0) for r in rows if r.ref_daily_sales
            )
            if ref_sales <= 0:
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
                    ref_daily_sales=ref_sales,
                    available=total_avail,
                    sales_metrics=sales_metrics,
                    scope=MonitoringScope.GLOBAL,
                )
            )
        return findings

    def _evaluate_channel_scope(self) -> list[MonitorFinding]:
        sales = (
            self.db.query(FactSalesDaily)
            .filter(FactSalesDaily.date == self.monitor_date, FactSalesDaily.sku.isnot(None))
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
                    FactInventoryDaily.date == self.monitor_date,
                    FactInventoryDaily.sku == sku_code,
                )
                .all()
            )
            total_avail = sum(r.available_inventory for r in inv_total)
            dos = Decimal(total_avail) / avg_daily if avg_daily > 0 else None
            if dos is None:
                continue
            sales_metrics = self._sales_metrics(sku_code, channel, MonitoringScope.CHANNEL)
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
        self, sku: str, warehouse: str | None, scope: MonitoringScope
    ) -> dict[str, Decimal]:
        q = self.db.query(FactSalesDaily).filter(
            FactSalesDaily.date <= self.monitor_date,
            FactSalesDaily.sku == sku,
        )
        if scope == MonitoringScope.CHANNEL and warehouse:
            q = q.filter(FactSalesDaily.channel == warehouse)
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
        ref_daily_sales: Decimal,
        available: int,
        sales_metrics: dict,
        scope: MonitoringScope = MonitoringScope.WAREHOUSE,
    ) -> list[MonitorFinding]:
        findings: list[MonitorFinding] = []
        stockout_red = _dos_threshold(seasonality, "DOS_RED_REG", "DOS_RED_SEA", self.cfg)
        slow_red = _dos_threshold(seasonality, "SLOW_DOS_RED_REG", "SLOW_DOS_RED_SEA", self.cfg)
        surge_ratio = self.cfg.get_float("SALES_SURGE_RATIO", 1.5)

        # 断货
        stockout_level = RiskLevel.GREEN
        if dos <= stockout_red:
            stockout_level = RiskLevel.RED
        elif dos <= stockout_red * Decimal("1.5"):
            stockout_level = RiskLevel.ORANGE
        elif dos <= stockout_red * Decimal("2"):
            stockout_level = RiskLevel.YELLOW

        s3 = sales_metrics.get("sales_3d_avg", ZERO)
        s15 = sales_metrics.get("sales_15d_avg", ZERO)
        if s15 > 0 and s3 >= s15 * Decimal(str(surge_ratio)):
            stockout_level = _upgrade(stockout_level, 1)

        relief_applied = False
        relief_note = None
        if (
            stockout_level == RiskLevel.RED
            and self.cfg.get_bool("INBOUND_RELIEF_DOWNGRADE")
            and scope == MonitoringScope.WAREHOUSE
            and warehouse
        ):
            if self._inbound_can_relief(sku, warehouse, dos, ref_daily_sales, available):
                stockout_level = RiskLevel.ORANGE
                relief_applied = True
                relief_note = "需关注到货兑现"

        if self.cfg.get_bool("KEY_SKU_UPGRADE") and is_key and stockout_level != RiskLevel.GREEN:
            stockout_level = _upgrade(stockout_level, 1)

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
                    trigger_metrics={
                        "dos": float(dos),
                        "threshold_red": stockout_red,
                        "sales_3d_avg": float(s3),
                        "sales_15d_avg": float(s15),
                    },
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
        slow_level = RiskLevel.GREEN
        if dos >= slow_red:
            slow_level = RiskLevel.RED
        elif dos >= slow_red * Decimal("0.85"):
            slow_level = RiskLevel.ORANGE
        elif dos >= slow_red * Decimal("0.7"):
            slow_level = RiskLevel.YELLOW

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
                    trigger_metrics={"dos": float(dos), "threshold_red": slow_red},
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
                    "sales_3d_avg": float(s3),
                    "sales_15d_avg": float(s15),
                    "ratio": float(s3 / s15) if s15 else None,
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
                FactInboundBatch.date == self.monitor_date,
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
