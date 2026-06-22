from datetime import date

from sqlalchemy.orm import Session

from buque.models.entities import DataQualityIssue, DimMskuMapping, FactInventoryDaily, FactSalesDaily


class DataQualityChecker:
    def __init__(self, db: Session, monitor_date: date):
        self.db = db
        self.monitor_date = monitor_date
        self.issues: list[DataQualityIssue] = []

    def run(self) -> list[DataQualityIssue]:
        self._check_negative_inventory()
        self._check_missing_mapping()
        self._check_missing_ref_sales()
        for issue in self.issues:
            self.db.add(issue)
        self.db.commit()
        return self.issues

    def _add(
        self,
        issue_code: str,
        message: str,
        sku: str | None = None,
        warehouse: str | None = None,
        field_name: str | None = None,
    ) -> None:
        self.issues.append(
            DataQualityIssue(
                date=self.monitor_date,
                sku=sku,
                warehouse=warehouse,
                issue_code=issue_code,
                issue_message=message,
                field_name=field_name,
            )
        )

    def _check_negative_inventory(self) -> None:
        rows = (
            self.db.query(FactInventoryDaily)
            .filter(FactInventoryDaily.date == self.monitor_date)
            .all()
        )
        for row in rows:
            if row.available_inventory < 0:
                self._add(
                    "NEGATIVE_INVENTORY",
                    f"可售库存为负: {row.available_inventory}",
                    sku=row.sku,
                    warehouse=row.warehouse,
                    field_name="available_inventory",
                )
            if row.on_hand_inventory and row.available_inventory > row.on_hand_inventory:
                self._add(
                    "INVENTORY_INCONSISTENT",
                    "可售库存大于总库存",
                    sku=row.sku,
                    warehouse=row.warehouse,
                )

    def _check_missing_mapping(self) -> None:
        sales = (
            self.db.query(FactSalesDaily)
            .filter(
                FactSalesDaily.date == self.monitor_date,
                FactSalesDaily.sku.is_(None),
            )
            .all()
        )
        for row in sales:
            mapped = (
                self.db.query(DimMskuMapping)
                .filter(
                    DimMskuMapping.msku == row.msku,
                    DimMskuMapping.channel == row.channel,
                )
                .first()
            )
            if not mapped:
                self._add(
                    "MSKU_MAPPING_MISSING",
                    f"MSKU {row.msku} 在渠道 {row.channel} 无映射",
                    field_name="msku",
                )

    def _check_missing_ref_sales(self) -> None:
        rows = (
            self.db.query(FactInventoryDaily)
            .filter(FactInventoryDaily.date == self.monitor_date)
            .all()
        )
        for row in rows:
            if row.ref_daily_sales is None:
                self._add(
                    "MISSING_REF_SALES",
                    "缺少7天日均(ref_daily_sales)",
                    sku=row.sku,
                    warehouse=row.warehouse,
                    field_name="ref_daily_sales",
                )
