"""API tokens for the MCP server, and integration accounts

Revision ID: 0013
Revises: 0012

- users.kind: "person", or "integration" for an account an Administrator
  makes for another system (it never signs in; it holds tokens).
- users.allowed_engines: the modes an account may start, null for all.
- api_tokens: a token's hash, never the token; its scopes, expiry, last
  use, and revocation (docs/adr/0009).
- runs.via_token_id: the token a Run was started with, for the Run card's
  "via MCP" badge and the Administrator's usage.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("kind", sa.String(20), nullable=False, server_default="person"))
    op.add_column("users", sa.Column("allowed_engines", JSONB))
    op.create_table(
        "api_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("prefix", sa.String(16), nullable=False),
        sa.Column("scopes", JSONB, nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("api_tokens_user", "api_tokens", ["user_id"])
    op.add_column(
        "runs", sa.Column("via_token_id", UUID(as_uuid=True), sa.ForeignKey("api_tokens.id", ondelete="SET NULL"))
    )


def downgrade():
    op.drop_column("runs", "via_token_id")
    op.drop_table("api_tokens")
    op.drop_column("users", "allowed_engines")
    op.drop_column("users", "kind")
