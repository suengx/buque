from datetime import date, datetime, timezone

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
from buque.services.snapshot_query import previous_snapshot


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


def _success_job(
    db: Session,
    *,
    job_id: int,
    monitor_date: date,
    finished_at: datetime,
) -> ErpSyncJob:
    job = ErpSyncJob(
        id=job_id,
        monitor_date=monitor_date,
        job_kind=JobKind.PIPELINE,
        phase=ErpSyncPhase.DONE,
        status=IngestionStatus.SUCCESS,
        phase_message="test",
        started_at=finished_at,
        finished_at=finished_at,
    )
    db.add(job)
    db.commit()
    return job


def test_previous_snapshot_returns_latest_prior_run(db_session: Session) -> None:
    md = date(2026, 6, 23)
    _success_job(
        db_session,
        job_id=1,
        monitor_date=md,
        finished_at=datetime(2026, 6, 23, 8, 0, tzinfo=timezone.utc),
    )
    _success_job(
        db_session,
        job_id=2,
        monitor_date=md,
        finished_at=datetime(2026, 6, 23, 14, 0, tzinfo=timezone.utc),
    )
    _success_job(
        db_session,
        job_id=3,
        monitor_date=md,
        finished_at=datetime(2026, 6, 23, 18, 0, tzinfo=timezone.utc),
    )

    prev = previous_snapshot(db_session, 3)
    assert prev is not None
    assert prev.id == 2

    assert previous_snapshot(db_session, 1) is None
