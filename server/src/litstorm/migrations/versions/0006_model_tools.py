"""Whether a model can call tools

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    # Unknown (null) until the model's test button is pressed.
    op.add_column("llm_models", sa.Column("supports_tools", sa.Boolean, nullable=True))


def downgrade():
    op.drop_column("llm_models", "supports_tools")
