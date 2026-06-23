from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from buque.models.entities import (
    ErpSyncJob,
    ErpSyncLog,
    ErpSyncPhase,
    IngestionRun,
    IngestionStatus,
    JobKind,
)
from buque.services.erp_sync_job import (
    build_pipeline_status,
    create_pipeline_job,
    finish_pipeline_success,
    has_running_pipeline_job,
    list_snapshots,
    update_job_phase,
)


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    for table in (
        ErpSyncJob.__table__,
        ErpSyncLog.__table__,
        IngestionRun.__table__,
    ):
        table.create(engine, checkfirst=True)
    factory = sessionmaker(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def test_pipeline_job_lifecycle(db_session: Session) -> None:
    md = date(2026, 6, 22)
    job = create_pipeline_job(db_session, md)
    assert job.job_kind == JobKind.PIPELINE
    assert has_running_pipeline_job(db_session)
    update_job_phase(db_session, job.id, ErpSyncPhase.EXPORTING, "正在导出…")
    status = build_pipeline_status(db_session, job.id)
    assert status.running is True
    assert status.phase == "EXPORTING"
    finish_pipeline_success(db_session, job.id, {"ingestion_counts": {"inventory": 1}}, {"monitor_results": 2})
    status = build_pipeline_status(db_session, job.id)
    assert status.job_status == "SUCCESS"
    assert not has_running_pipeline_job(db_session)
    snapshots = list_snapshots(db_session)
    assert len(snapshots) == 1
    assert snapshots[0].id == job.id


def test_two_snapshots_same_business_day(db_session: Session) -> None:
    md = date(2026, 6, 23)
    job1 = create_pipeline_job(db_session, md)
    finish_pipeline_success(db_session, job1.id, {}, {"monitor_results": 1})
    job2 = create_pipeline_job(db_session, md)
    finish_pipeline_success(db_session, job2.id, {}, {"monitor_results": 2})

    snapshots = list_snapshots(db_session)
    assert len(snapshots) == 2
    assert {s.id for s in snapshots} == {job1.id, job2.id}
    assert all(s.monitor_date == md for s in snapshots)
