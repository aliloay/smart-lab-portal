"""One scale, several items (2026-11-20, owner).

Additive only: one new table, inventory_bin_items - a saved calibration per kind of part a bin's scale can hold
(10k resistors, M3 screws, ...). The bin row keeps the ACTIVE item's values, so counting is unchanged; selecting
another item copies its saved values back. The data step only INSERTS: one item per calibrated bin, from its
current values, marked selected. No existing row changes. Downgrade removes the table.
"""
import sqlalchemy as sa
from alembic import op

revision = "a7b3c9d1e240"
down_revision = "f1a7c3d9e250"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "inventory_bin_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bin_id", sa.Integer(), sa.ForeignKey("inventory_bins.id"), nullable=False, index=True),
        sa.Column("item_name", sa.String(64), nullable=False),
        sa.Column("category", sa.String(32), nullable=False, server_default="component"),
        sa.Column("tare_g", sa.Float(), nullable=True),
        sa.Column("unit_mass_g", sa.Float(), nullable=True),
        sa.Column("noise_g", sa.Float(), nullable=True),
        sa.Column("reorder_qty", sa.Integer(), nullable=True),
        sa.Column("stock_max", sa.Integer(), nullable=True),
        sa.Column("calibrated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_selected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.execute("""
        INSERT INTO inventory_bin_items (bin_id, item_name, category, tare_g, unit_mass_g, noise_g, reorder_qty,
                                         stock_max, calibrated_at, is_selected)
        SELECT id, item_name, category, tare_g, unit_mass_g, noise_g, reorder_qty, stock_max, calibrated_at, true
        FROM inventory_bins WHERE unit_mass_g IS NOT NULL
    """)


def downgrade():
    op.drop_table("inventory_bin_items")
