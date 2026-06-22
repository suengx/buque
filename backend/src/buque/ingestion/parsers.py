from __future__ import annotations

import hashlib
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from buque.config import get_settings
from buque.models.entities import (
    DimMskuMapping,
    DimSku,
    FactInboundBatch,
    FactInventoryDaily,
    FactSalesDaily,
    IngestionRun,
    IngestionStatus,
)
from buque.services.rule_config import RuleConfigService

settings = get_settings()
TMS_ELIGIBLE_DEFAULT = {"已出运", "入库中"}


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _start_run(db: Session, source: str, file_path: Path | None) -> IngestionRun:
    run = IngestionRun(
        source=source,
        file_path=str(file_path) if file_path else None,
        file_hash=_file_hash(file_path) if file_path and file_path.exists() else None,
        status=IngestionStatus.RUNNING,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _finish_run(db: Session, run: IngestionRun, row_count: int, error: str | None = None) -> None:
    run.finished_at = datetime.now(settings.tz)
    run.row_count = row_count
    run.status = IngestionStatus.FAILED if error else IngestionStatus.SUCCESS
    run.error_message = error
    db.commit()


def _ensure_sku(db: Session, sku: str, product_name: str | None = None) -> None:
    if db.get(DimSku, sku):
        return
    db.add(DimSku(sku=sku, product_name=product_name))


def _resolve_sku(db: Session, msku: str, channel: str) -> str | None:
    mapping = (
        db.query(DimMskuMapping)
        .filter(DimMskuMapping.msku == msku, DimMskuMapping.channel == channel)
        .first()
    )
    return mapping.sku if mapping else None


class InventoryParser:
    COLUMN_MAP = {
        "SKU": "sku",
        "sku": "sku",
        "产品SKU": "sku",
        "仓库": "warehouse",
        "warehouse": "warehouse",
        "可售库存": "available_inventory",
        "available_inventory": "available_inventory",
        "锁定库存": "reserved_inventory",
        "reserved_inventory": "reserved_inventory",
        "总库存": "on_hand_inventory",
        "on_hand_inventory": "on_hand_inventory",
        "7天日均": "ref_daily_sales",
        "ref_daily_sales": "ref_daily_sales",
        "周转天数": "turnover_days",
        "turnover_days": "turnover_days",
        "在途量": "in_transit_no_eta",
        "in_transit_no_eta": "in_transit_no_eta",
        "产品名称": "product_name",
        "product_name": "product_name",
    }

    def __init__(self, db: Session, monitor_date: date):
        self.db = db
        self.monitor_date = monitor_date

    def ingest_file(self, path: Path) -> int:
        run = _start_run(self.db, "erp_inventory", path)
        try:
            count = self._parse(path)
            _finish_run(self.db, run, count)
            return count
        except Exception as exc:
            _finish_run(self.db, run, 0, str(exc))
            raise

    def _parse(self, path: Path) -> int:
        df = pd.read_excel(path) if path.suffix.lower() in {".xlsx", ".xls"} else pd.read_csv(path)
        df = df.rename(columns={c: self.COLUMN_MAP[c] for c in df.columns if c in self.COLUMN_MAP})
        required = {"sku", "warehouse", "available_inventory"}
        if not required.issubset(df.columns):
            raise ValueError(f"库存文件缺少必要列: {required - set(df.columns)}")

        count = 0
        for _, row in df.iterrows():
            sku = str(row["sku"]).strip()
            if not sku or sku == "nan":
                continue
            product_name = str(row.get("product_name", "")).strip() or None
            _ensure_sku(self.db, sku, product_name)
            warehouse = str(row["warehouse"]).strip()

            existing = (
                self.db.query(FactInventoryDaily)
                .filter(
                    FactInventoryDaily.date == self.monitor_date,
                    FactInventoryDaily.sku == sku,
                    FactInventoryDaily.warehouse == warehouse,
                )
                .first()
            )
            payload = dict(
                date=self.monitor_date,
                sku=sku,
                warehouse=warehouse,
                available_inventory=int(row.get("available_inventory", 0) or 0),
                reserved_inventory=int(row.get("reserved_inventory", 0) or 0),
                on_hand_inventory=int(row.get("on_hand_inventory", 0) or 0),
                in_transit_no_eta=int(row.get("in_transit_no_eta", 0) or 0),
                ref_daily_sales=row.get("ref_daily_sales"),
                turnover_days=row.get("turnover_days"),
            )
            if existing:
                for k, v in payload.items():
                    setattr(existing, k, v)
            else:
                self.db.add(FactInventoryDaily(**payload))
            count += 1
        self.db.commit()
        return count


class OrdersParser:
    COLUMN_MAP = {
        "MSKU": "msku",
        "msku": "msku",
        "平台": "channel",
        "channel": "channel",
        "订购数量": "order_qty",
        "order_qty": "order_qty",
        "订购时间(市场)": "order_date",
        "order_date": "order_date",
        "仓库": "warehouse",
        "warehouse": "warehouse",
    }

    def __init__(self, db: Session, monitor_date: date):
        self.db = db
        self.monitor_date = monitor_date

    def ingest_file(self, path: Path) -> int:
        run = _start_run(self.db, "erp_orders", path)
        try:
            count = self._parse(path)
            _finish_run(self.db, run, count)
            return count
        except Exception as exc:
            _finish_run(self.db, run, 0, str(exc))
            raise

    def _parse(self, path: Path) -> int:
        df = pd.read_excel(path) if path.suffix.lower() in {".xlsx", ".xls"} else pd.read_csv(path)
        df = df.rename(columns={c: self.COLUMN_MAP[c] for c in df.columns if c in self.COLUMN_MAP})
        if "order_date" in df.columns:
            df["order_date"] = pd.to_datetime(df["order_date"]).dt.date
            df = df[df["order_date"] == self.monitor_date]
        if "msku" not in df.columns or "channel" not in df.columns:
            raise ValueError("订单文件缺少 msku/channel 列")

        count = 0
        grouped = df.groupby(["msku", "channel"], dropna=False).agg({"order_qty": "sum"}).reset_index()
        for _, row in grouped.iterrows():
            msku = str(row["msku"]).strip()
            channel = str(row["channel"]).strip()
            sku = _resolve_sku(self.db, msku, channel)
            existing = (
                self.db.query(FactSalesDaily)
                .filter(
                    FactSalesDaily.date == self.monitor_date,
                    FactSalesDaily.msku == msku,
                    FactSalesDaily.channel == channel,
                )
                .first()
            )
            if existing:
                existing.order_qty = int(row.get("order_qty", 0) or 0)
                existing.sku = sku
            else:
                self.db.add(
                    FactSalesDaily(
                        date=self.monitor_date,
                        msku=msku,
                        channel=channel,
                        sku=sku,
                        order_qty=int(row.get("order_qty", 0) or 0),
                    )
                )
            count += 1
        self.db.commit()
        return count


class InboundParser:
    COLUMN_MAP = {
        "SKU": "sku",
        "sku": "sku",
        "目的仓": "warehouse",
        "warehouse": "warehouse",
        "批次号": "batch_id",
        "batch_id": "batch_id",
        "ETA": "eta_date",
        "eta_date": "eta_date",
        "TMS状态": "tms_status",
        "tms_status": "tms_status",
        "未收量": "unreceived_qty",
        "unreceived_qty": "unreceived_qty",
    }

    def __init__(self, db: Session, monitor_date: date, rule_config: RuleConfigService):
        self.db = db
        self.monitor_date = monitor_date
        self.eligible_statuses = set(rule_config.get_list("INBOUND_TMS_ELIGIBLE"))

    def ingest_file(self, path: Path) -> int:
        run = _start_run(self.db, "tms_inbound", path)
        try:
            count = self._parse(path)
            _finish_run(self.db, run, count)
            return count
        except Exception as exc:
            _finish_run(self.db, run, 0, str(exc))
            raise

    def _parse(self, path: Path) -> int:
        df = pd.read_excel(path) if path.suffix.lower() in {".xlsx", ".xls"} else pd.read_csv(path)
        df = df.rename(columns={c: self.COLUMN_MAP[c] for c in df.columns if c in self.COLUMN_MAP})
        required = {"sku", "warehouse", "batch_id"}
        if not required.issubset(df.columns):
            raise ValueError(f"在途文件缺少必要列: {required - set(df.columns)}")

        count = 0
        for _, row in df.iterrows():
            sku = str(row["sku"]).strip()
            _ensure_sku(self.db, sku)
            eta = row.get("eta_date")
            eta_date = pd.to_datetime(eta).date() if pd.notna(eta) else None
            tms_status = str(row.get("tms_status", "")).strip() or None
            eligible = bool(
                eta_date and tms_status and tms_status in self.eligible_statuses
            )
            existing = (
                self.db.query(FactInboundBatch)
                .filter(
                    FactInboundBatch.date == self.monitor_date,
                    FactInboundBatch.sku == sku,
                    FactInboundBatch.warehouse == str(row["warehouse"]).strip(),
                    FactInboundBatch.batch_id == str(row["batch_id"]).strip(),
                )
                .first()
            )
            payload = dict(
                date=self.monitor_date,
                sku=sku,
                warehouse=str(row["warehouse"]).strip(),
                batch_id=str(row["batch_id"]).strip(),
                eta_date=eta_date,
                tms_status=tms_status,
                unreceived_qty=int(row.get("unreceived_qty", 0) or 0),
                eligible_for_relief=eligible,
            )
            if existing:
                for k, v in payload.items():
                    setattr(existing, k, v)
            else:
                self.db.add(FactInboundBatch(**payload))
            count += 1
        self.db.commit()
        return count
