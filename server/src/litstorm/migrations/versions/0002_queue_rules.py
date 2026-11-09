"""Queue rules: whose turn it is, and one Run per submitted request

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    # When this User's most recent Run started; the queue serves whoever has
    # waited longest since their last turn.
    op.add_column("users", sa.Column("last_run_started_at", sa.DateTime(timezone=True)))
    # The browser's id for one press of "Start": the same request twice makes
    # one Run, not two.
    op.add_column("runs", sa.Column("request_key", sa.String(64)))
    op.create_index(
        "runs_one_per_request",
        "runs",
        ["owner_id", "request_key"],
        unique=True,
        postgresql_where=sa.text("request_key is not null"),
    )
    op.create_index("runs_owner_month", "runs", ["owner_id", "quota_month"])


def downgrade():
    op.drop_index("runs_owner_month", table_name="runs")
    op.drop_index("runs_one_per_request", table_name="runs")
    op.drop_column("runs", "request_key")
    op.drop_column("users", "last_run_started_at")
