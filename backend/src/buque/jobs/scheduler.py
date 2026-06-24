from __future__ import annotations

import logging
import os
from datetime import date

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy.orm import Session

from buque.config import get_settings
from buque.db import SessionLocal
from buque.services.erp_sync_job import create_pipeline_job
from buque.services.schedule_config import daily_pipeline_trigger, schedule_label
from buque.services.sync_pipeline import run_pipeline_job

logger = logging.getLogger(__name__)
settings = get_settings()


def run_daily_pipeline(monitor_date: date | None = None, use_fixtures: bool | None = None) -> None:
    md = monitor_date or date.today()
    db: Session = SessionLocal()
    try:
        if use_fixtures is None:
            use_fixtures = not bool(settings.erp_base_url)
        if use_fixtures:
            ingestion = "fixtures"
        elif settings.erp_base_url:
            ingestion = "erp"
        else:
            logger.warning("ERP 未配置，跳过抓取")
            return

        job = create_pipeline_job(db, md)
        run_pipeline_job(db, md, job.id, ingestion=ingestion)
        logger.info("日批完成: %s snapshot=%s ingestion=%s", md.isoformat(), job.id, ingestion)
    finally:
        db.close()


def run_daily_pipeline_cli() -> None:
    logging.basicConfig(level=logging.INFO)
    use_erp = os.environ.get("BUQUE_USE_ERP", "").lower() in {"1", "true", "yes"}
    if use_erp:
        run_daily_pipeline(use_fixtures=False)
    else:
        run_daily_pipeline(use_fixtures=True)


def start_scheduler() -> None:
    logging.basicConfig(level=logging.INFO)
    scheduler = BlockingScheduler(timezone=str(settings.tz))
    scheduler.add_job(
        run_daily_pipeline,
        daily_pipeline_trigger(settings.tz),
        id="buque_daily_pipeline",
        replace_existing=True,
    )
    logger.info("调度器已启动 %s 日批", schedule_label())
    scheduler.start()


if __name__ == "__main__":
    start_scheduler()
