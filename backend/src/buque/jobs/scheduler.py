from __future__ import annotations

import logging
import os
from datetime import date

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from buque.config import get_settings
from buque.db import SessionLocal
from buque.services.sync_pipeline import run_analysis_pipeline, run_sync_ingestion

logger = logging.getLogger(__name__)
settings = get_settings()


def run_daily_pipeline(monitor_date: date | None = None, use_fixtures: bool = False) -> None:
    md = monitor_date or date.today()
    db: Session = SessionLocal()
    try:
        if use_fixtures:
            ingestion = "fixtures"
        elif settings.erp_base_url:
            ingestion = "erp"
        else:
            logger.warning("ERP 未配置，跳过抓取")
            return

        run_sync_ingestion(db, md, ingestion=ingestion)
        run_analysis_pipeline(db, md)
        logger.info("日批完成: %s", md.isoformat())
    finally:
        db.close()


def run_daily_pipeline_cli() -> None:
    logging.basicConfig(level=logging.INFO)
    use_erp = os.environ.get("BUQUE_USE_ERP", "").lower() in {"1", "true", "yes"}
    run_daily_pipeline(use_fixtures=not use_erp)


def start_scheduler() -> None:
    logging.basicConfig(level=logging.INFO)
    scheduler = BlockingScheduler(timezone=str(settings.tz))
    scheduler.add_job(
        run_daily_pipeline,
        CronTrigger(hour=6, minute=0, timezone=settings.tz),
        id="buque_daily_pipeline",
        replace_existing=True,
    )
    logger.info("调度器已启动 Asia/Shanghai 06:00 日批")
    scheduler.start()


if __name__ == "__main__":
    start_scheduler()
