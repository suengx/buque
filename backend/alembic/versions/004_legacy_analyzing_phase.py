"""Normalize legacy ANALYZING phase on erp_sync_job."""

from typing import Sequence, Union

from alembic import op

revision: str = "004_legacy_analyzing_phase"
down_revision: Union[str, None] = "003_job_kind_sync_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE erp_sync_job
        SET
            phase = 'DONE',
            status = 'FAILED',
            error_message = COALESCE(error_message, '任务超时或进程中断，已自动释放'),
            finished_at = COALESCE(finished_at, NOW())
        WHERE phase = 'ANALYZING'
          AND status = 'RUNNING'
        """
    )
    op.execute(
        """
        UPDATE erp_sync_job
        SET phase = 'DONE'
        WHERE phase = 'ANALYZING'
        """
    )


def downgrade() -> None:
    pass
