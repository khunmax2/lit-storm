"""Trash that purges content but keeps accounting; token and cost totals

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    # A purged Run keeps its row, without content or Session, so the months
    # its quota and cost belong to do not change after the fact.
    op.alter_column("runs", "session_id", nullable=True)
    op.add_column("runs", sa.Column("purged_at", sa.DateTime(timezone=True)))
    op.add_column("runs", sa.Column("tokens_in", sa.BigInteger))
    op.add_column("runs", sa.Column("tokens_out", sa.BigInteger))
    op.add_column("runs", sa.Column("search_calls", sa.Integer))
    # Estimated, in US dollars (docs/web-app-design.md: ค่าประมาณ).
    op.add_column("runs", sa.Column("cost_usd", sa.Numeric(12, 6)))
    # What an Administrator says one million tokens cost, when the price
    # table does not know the model.
    op.add_column("llm_models", sa.Column("price_in_per_mtok", sa.Numeric(10, 4)))
    op.add_column("llm_models", sa.Column("price_out_per_mtok", sa.Numeric(10, 4)))
    op.create_index("runs_trashed", "runs", ["trashed_at"], postgresql_where=sa.text("trashed_at is not null"))


def downgrade():
    op.drop_index("runs_trashed", table_name="runs")
    op.drop_column("llm_models", "price_out_per_mtok")
    op.drop_column("llm_models", "price_in_per_mtok")
    op.drop_column("runs", "cost_usd")
    op.drop_column("runs", "search_calls")
    op.drop_column("runs", "tokens_out")
    op.drop_column("runs", "tokens_in")
    op.drop_column("runs", "purged_at")
    op.alter_column("runs", "session_id", nullable=False)
