"""What a Run's owner should know about how it went

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    # Kept on the Run rather than read from its events, so a list of Runs
    # shows them without reading every Run's events (queue.NOTE_KINDS).
    op.add_column("runs", sa.Column("notes", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")))


def downgrade():
    op.drop_column("runs", "notes")
