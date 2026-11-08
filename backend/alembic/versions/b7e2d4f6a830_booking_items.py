"""Booking equipment: booking_items.

Only a new table - nothing existing is changed or dropped.

Revision ID: b7e2d4f6a830
Revises: a3c5e7f9b124
"""
import sqlalchemy as sa
from alembic import op

revision = 'b7e2d4f6a830'
down_revision = 'a3c5e7f9b124'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "booking_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("booking_id", sa.Integer, sa.ForeignKey("bookings.id"), nullable=False, index=True),
        sa.Column("kind", sa.String(16), nullable=False, index=True),
        sa.Column("asset_id", sa.Integer, sa.ForeignKey("assets.id"), nullable=True, index=True),
        sa.Column("inventory_bin_id", sa.Integer, sa.ForeignKey("inventory_bins.id"), nullable=True),
        sa.Column("quantity", sa.Integer, nullable=True),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    # Never drops booking history automatically (data is the product).
    raise RuntimeError("booking_items holds booking history; not dropped by a downgrade")
