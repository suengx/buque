"""初始化数据库：迁移 + rule_config 种子 + fixture 维度数据。"""

from pathlib import Path

import pandas as pd
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from buque.db import SessionLocal, engine
from buque.models.entities import DimMskuMapping, DimSku
from buque.services.rule_config import seed_rule_config


def run_migrations() -> None:
    alembic_cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")


def load_fixture_dimensions(db: Session) -> None:
    base = Path(__file__).resolve().parents[1] / "fixtures"
    skus = pd.read_csv(base / "focus_skus.csv")
    for _, row in skus.iterrows():
        sku_code = str(row["sku"])
        existing = db.get(DimSku, sku_code)
        if existing:
            existing.product_name = str(row.get("product_name", ""))
            existing.item_grade = str(row.get("item_grade", "")) or None
            existing.seasonality = str(row.get("seasonality", "")) or None
            existing.category = str(row.get("category", "")) or None
            existing.is_key_listing = bool(row.get("is_key_listing", False))
            existing.is_focus_sku = bool(row.get("is_focus_sku", False))
        else:
            db.add(
                DimSku(
                    sku=sku_code,
                    product_name=str(row.get("product_name", "")),
                    item_grade=str(row.get("item_grade", "")) or None,
                    seasonality=str(row.get("seasonality", "")) or None,
                    category=str(row.get("category", "")) or None,
                    is_key_listing=bool(row.get("is_key_listing", False)),
                    is_focus_sku=bool(row.get("is_focus_sku", False)),
                )
            )
    db.commit()
    mappings = pd.read_csv(base / "msku_mapping.csv")
    for _, row in mappings.iterrows():
        existing = (
            db.query(DimMskuMapping)
            .filter(
                DimMskuMapping.msku == row["msku"],
                DimMskuMapping.channel == row["channel"],
            )
            .first()
        )
        if existing:
            continue
        db.add(
            DimMskuMapping(
                msku=str(row["msku"]),
                channel=str(row["channel"]),
                sku=str(row["sku"]),
                store=str(row.get("store", "")) or None,
            )
        )
    db.commit()


def main() -> None:
    run_migrations()
    db = SessionLocal()
    try:
        inserted = seed_rule_config(db)
        load_fixture_dimensions(db)
        print(f"rule_config seeded: {inserted} rows")
    finally:
        db.close()
    print("init complete")


if __name__ == "__main__":
    main()
