"""A Project's defaults for new research, and its two instructions

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("projects", sa.Column("defaults", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("projects", sa.Column("search_scope", sa.Text))
    op.add_column("projects", sa.Column("writing_style", sa.Text))


def downgrade():
    op.drop_column("projects", "writing_style")
    op.drop_column("projects", "search_scope")
    op.drop_column("projects", "defaults")
