"""inventory bins: how many pieces the lab owns (additive)

A rise above this is load-cell fluctuation, never a refill.

Revision ID: a9d3f1c7b520
Revises: c4f8a2e6d913
"""
from alembic import op
import sqlalchemy as sa

revision = 'a9d3f1c7b520'
down_revision = 'c4f8a2e6d913'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('inventory_bins', sa.Column('stock_max', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('inventory_bins', 'stock_max')
