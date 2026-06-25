"""DATA_ANOMALY rows should not use ORANGE risk level."""

from typing import Sequence, Union

from alembic import op

revision: str = "010_data_anomaly_not_orange"
down_revision: Union[str, None] = "009_chat"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE fact_monitor_result
        SET risk_level = 'GREEN'
        WHERE risk_type = 'DATA_ANOMALY' AND risk_level = 'ORANGE'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE fact_monitor_result
        SET risk_level = 'ORANGE'
        WHERE risk_type = 'DATA_ANOMALY' AND risk_level = 'GREEN'
        """
    )
