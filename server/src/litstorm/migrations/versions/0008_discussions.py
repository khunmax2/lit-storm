"""Discussions: a Research Session of Turns, and quota counted in units

A Discussion (docs/CONTEXT.md) is a Research Session whose Runs are Turns.
A Turn is a Run row, so it queues, leases, stops and costs like one; `turn`
says what it does. Quota was one unit per Run; now each Run carries its
units: 1 for an ordinary Run and for the Turn that opens a block of Turns,
0 for the other Turns of the block.

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "research_sessions", sa.Column("kind", sa.String(20), nullable=False, server_default="research")
    )
    op.add_column("runs", sa.Column("turn", JSONB))
    op.add_column("runs", sa.Column("quota_units", sa.Integer, nullable=False, server_default="1"))


def downgrade():
    op.drop_column("runs", "quota_units")
    op.drop_column("runs", "turn")
    op.drop_column("research_sessions", "kind")
