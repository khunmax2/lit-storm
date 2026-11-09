"""Research Sessions that belong to no Project

Revision ID: 0004
Revises: 0003
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    # Research started from the home page needs no Project; the owner can
    # file it in one later, or never (docs/CONTEXT.md, Project).
    op.alter_column("research_sessions", "project_id", nullable=True)


def downgrade():
    # Refuses while any Session has no Project: file them first.
    op.alter_column("research_sessions", "project_id", nullable=False)
