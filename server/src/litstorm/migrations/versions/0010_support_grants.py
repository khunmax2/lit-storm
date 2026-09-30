"""Support Access Grants and their access log

Revision ID: 0010
Revises: 0009
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "support_grants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("admin_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("runs.id", ondelete="CASCADE")),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("research_sessions.id", ondelete="CASCADE")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("(run_id is null) <> (session_id is null)", name="support_grants_one_target"),
    )
    for column in ("owner_id", "admin_id", "run_id", "session_id"):
        op.create_index(f"ix_support_grants_{column}", "support_grants", [column])
    op.create_table(
        "support_access",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("grant_id", UUID(as_uuid=True), sa.ForeignKey("support_grants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("what", sa.String(40), nullable=False),
    )
    op.create_index("ix_support_access_grant_id", "support_access", ["grant_id"])


def downgrade():
    op.drop_table("support_access")
    op.drop_table("support_grants")
